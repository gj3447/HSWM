# 의미 보존 구조 변경과 W 재결속 — 첫 실행 범위

2026-10-19 · agent(codex) 구현·검증 기록. [작업 계획](HSWM_SEMANTIC_W_OPTIMIZATION_PLAN_2026-10-18.md)의 후속이며,
동결된 계획과 이전 실험 수치를 수정하지 않는다.

**현재: 실모델 P01 실패, 비교 중단. HSWM_LIKENESS의 별도 정책 연결은 현재 코드 재검증 통과.**
아래의 최초 구현·리허설 기록 뒤에 [실제 실행과 연결 확인](#실제-실행과-hswm_likeness-연결-확인)을 추가했다.

**실행 결과로 학습한 W → 의미 보존 후보 → owner의 구조·W 동시 채택 → 다음 프로세스의 재사용**을
기존 native runtime에 연결했다. 첫 구조 변환은 **특정 후보 묶음에서 중복 관계의 활성 연결을 퇴역시키는 것**이다.
원본 관계·역할·과거 revision은 남으며, 전역 노드 삭제·새 허브 생성·자유로운 분할/병합은 이번 구현 범위가 아니다.

## 구현된 루프

1. `execute`의 `presentation: execution_tail`은 전체 canonical frame 뒤에 실행할 규칙 원문을 다시 제시한다.
   기본 `canonical_json`과 기존 v1 기록은 유지한다. 새 v2 요청은 정확한 prompt와 UTF-8 길이를 저장한다.
   반복 원문까지 `maximumContextBytes`에 포함하며 초과 시 호출 전에 거부한다.
2. 실행 trace에 HTTP adapter 경계의 요청·응답 body descriptor를 결속한다. 헤더·인증 정보는 저장하지 않는다.
   `learn`은 canonical assembly, 재생성한 prompt, 관측 wire, 실제 prediction을 대조한 뒤 기존 LinUCB를 갱신한다.
   호출자가 주입한 transport 아래에서 추가 변조가 없었다는 원격 인증은 아니다.
3. `topology-propose`는 현재 admitted W와 그 W를 만든 피드백을 읽고 최대 8개 퇴역 후보를 검사한다.
   변경할 묶음에 선언한 최소 실행 관측이 없으면 후보로 승격하지 않는다. TRAIN 여부·reward 출처는 caller 선언이다.
   bundle 보상을 개별 연결의 인과 기여로 나누지 않으며, degree·낮은 빈도로 관계를 제거하지 않는다.
4. `topology-change`는 변경 후보를 다시 검증한다. 모든 후보 묶음의 전체 유한 논리곱을 비교하고,
   정확한 role occurrence·participant key/owner/content·예외 참조·유한 예외 의존을 보존한다.
   개별적으로 중복인 두 제약을 동시에 제거해 전체 의미가 달라지면 거부한다.
5. 구조 정책과 초기화된 활성화 정책을 **하나의 content-bound owner 트랜잭션**으로 제안한다.
   CLI는 자동 submit하지 않는다. 기존 writer가 schema·권한·read-set·expected revision을 검사한다.
   구조만 저장되고 이전 W가 새 scope에 적용되는 중간 상태를 만들지 않는다. A/b는 복사하지 않고 재학습한다.
6. `topology-read`는 영속 그래프에서 문맥 spec과 해당 scope의 최신 W를 읽는다.
   `RESTORE`는 정확한 직전 scope로 새 revision을 추가하고 W를 다시 초기화한다. 이력 삭제나 과거 W 재사용은 하지 않는다.

변경은 해석기 TS에 매번 코드를 생성하는 방식이 아니다. 활성 관계 목록·W 수치·review 및 feedback 참조가
native `semantic_context_policy` atom의 content에 들어간다. topology는 새 media type을 쓰고 활성화 정책과 UID를 구별한다.
기존 `hswm:context-policy:scope`의 `candidate-root` 참조와 `hswm:reference:supersedes`를 재사용한다.
RDF projection은 기존 native 경로를 따른다. JSON의 수치·세부 spec은 content descriptor를 따라 원문에서 읽는다.

## 의미 보존의 경계

- `hswm-finite-semantic-program/v1`로 명시된 의미만 비교한다. 자연어·과도한 변수 공간은 `TOPOLOGY_UNKNOWN`이다.
- 전체 묶음의 변수 16개·완전한 할당 4,096개 상한을 적용한다. 한 노드씩 검사한 결과를 전체 보존으로 합치지 않는다.
- 같은 문장이라도 역할·출처의 exact participant가 다르면 합치지 않는다. 필수 규칙·후보 ID·예산을 바꾸는 요청도 거부한다.
- 대상 밖 canonical atom은 변경하지 않는다. 임의의 다른 자연어 과제·장기 학습 행동의 동치 증명은 아니다.
- topology scope 변경은 다음 학습의 가정을 바꾸므로 통계를 초기화한다. 현재 출력 의미의 동치와 미래 학습 동치를 구분한다.
- 기존 LinUCB의 정확한 동점은 선언 순서를 따른다. 다른 수치 해법 사이의 거의 같은 점수에 대한 재현성 보장은 추가 작업이다.

## CLI와 소유 경로

```bash
src/hswm/effect-runtime/bin/hswm-activation --help
node _research/semantic_w_loop_v1/run.mjs --check
```

기존 activation stdin 계약에 추가한 동작:

| 동작 | 입력 | 반환/효과 |
|---|---|---|
| execute | 기존 decision/cell + 선택적 presentation | 실제 호출, 원문·wire 결속 trace; canonical submit 없음 |
| topology-propose | basis: policyKey/feedbackContent/TRAIN/minimumObservations + maximumCandidates | 유한 후보와 거부/UNKNOWN 사유 |
| topology-change | operation/afterSpec/policyKey/basis/priorTopologyKey/topologyTarget/activationTarget | 구조·reset W의 원자적 변경 제안 |
| topology-read | topologyKey + spec.event | 저장한 scope와 최신 policyKey; caller의 나머지 spec으로 덮어쓰지 않음 |

RETIRE에는 실제 학습된 정책의 basis가 필요하다. RESTORE는 `basis:null`, 현재 topology key와 정확한 predecessor spec을 사용한다.
두 target은 서로 다른 lineage여야 하며 owner·scope·authorization·시각은 같아야 한다. 이후 실행은 반환한 새 policyKey를 사용한다.

## P00–P07 진행과 실험 준비

| 계획 | 이번 상태 | 남은 연결 |
|---|---|---|
| P00 | 첫 유한 퇴역 protocol 고정, 후속 승인·등록 갱신·reachability 확인 | 후속 전달 진단은 새 범위를 고정 |
| P01 | 전달·prompt/wire 결속 구현; 실모델 다섯 번째 개발 입력 실패 | 새 유한 규칙의 실모델 실행 충실도 회복 |
| P02 | 로컬 학습·중복 거부 검사; 이번 실모델 학습 미실행 | P01 통과 후 새 실모델 cohort와 수치 근접 동점 재현성 |
| P03 | 전체 유한 묶음·역할·예외 보존 검사 | 임의 자연어 추상화, 새 분해/허브 의미 검증 |
| P04 | 지원된 묶음의 제한된 중복 연결 퇴역 후보 | 허브 생성·분할·병합 proposer와 조합 기여 평가 |
| P05 | 구조·reset W 동시 owner 채택 검사 | 실모델 실행과 동일한 연구 저장소에서의 채택 |
| P06 | 별도 OS 프로세스 실행, 중복 거부, append-only 복원 검사 | 실모델 후속 실행 |
| P07 | 2×2 비교 실행기 준비; 실제 실행은 P01에서 중단 | 충실도 통과 후 별도 비교, 실패 prefix는 보존 |

실험은 기존 Boolean 사례의 새 입력과 명시적 유한 규칙으로 제한한다. 두 번의 별도 저장소 반복이며,
독립 자연 과제나 통계적 iid 표본으로 세지 않는다. 각 반복은 개발 8회, B0 8회, 학습 8회, B1 8회,
구조 변경 후 reset B2 8회, 재학습 8회, B3 8회, 새 프로세스 2회로 **58회, 전체 116회**다.
상한은 120회·동시성 1·전체 30분·호출당 30초·max_tokens 512다. 모델은 기존 `qwen3-4b-real`이다.
provider의 정확한 weight revision·sampling 설정은 미인증이며, 독립 seed 비교라고 부르지 않는다.

B0는 원래 구조/초기 W, B1은 원래 구조/학습 W, B2는 퇴역 구조/reset W, B3는 퇴역 구조/재학습 W다.
B2의 제거 대상은 결과 전에 `rule:duplicate`로 고정하며 holdout으로 고르지 않는다. 모든 조건은 같은 표현을 사용한다.
개발 의미 실행 위반은 0이어야 다음 단계로 간다. W 개선은 보류 정답 수가 엄격히 증가해야 하며,
구조 효율은 정확도 손실·예외 위반 없이 context bytes가 줄어야 해당 유한 범위에서 보고한다.
정책/표현/허용치를 결과에 맞춰 조정하지 않는다. 실패·부분 실행이면 미완료로 남기고 재시도하지 않는다.

학습·구조 검토·reset 후 재학습 비용을 모두 총예산에 포함한다. 프레임 크기, 전체 prompt bytes,
provider token 보고와 HTTP 시간을 분리하고 GPU FLOPs나 전력으로 환산하지 않는다.
같은 holdout을 네 조건에서 비교하지만 train이나 선택에 넣지 않는다. 두 반복 결과를 개별 보고하며
작은 작성 사례의 반복을 모집단 신뢰구간이나 일반 효능으로 확장하지 않는다. 조건 순서와 공유 서버 부하는 통제되지 않았다.

```bash
# CELL_JSON/REGISTRATION_JSON과 실제 저장소는 ignored private 경로에 둔다.
node _research/semantic_w_loop_v1/run.mjs --prepare NEW_OUTPUT CELL_JSON
node _research/semantic_w_loop_v1/run.mjs --run PREPARED_OUTPUT CELL_JSON REGISTRATION_JSON
# 별도 로컬 검증: 실모델/등록을 사용하지 않는 명시적 scripted backend
node _research/semantic_w_loop_v1/run.mjs --rehearse NEW_REHEARSAL_OUTPUT
```

`--prepare`가 쓰는 protocol을 `--run`이 실제 읽는다. protocol hash·cell hash·source/build pin,
명시적 승인·수신자·전송 경로·만료·철회·최근 성공 reachability를 검사한다. protocol을 바꾸어 기존 등록을 재사용할 수 없다.
raw 응답·trace·native 저장소는 private 출력에 남기며, 요청 실패와 부분 실행을 삭제하지 않는다.
`--rehearse`는 동일한 두 cohort를 유한 해석기로 실행하고 `actualProviderCalls:0`과
`SCRIPTED_REHEARSAL_NOT_MODEL_EVIDENCE`를 출력한다. 이 모드의 높은 정답률은 LLM 학습 결과가 아니다.

최초 구현 시점에는 기존 등록이 **2026-10-19 00:00 UTC에 만료**돼 새 모델 호출 **0회**,
원격 경로 `NOT_READY`였다. [OWNER의 USL workspace linking](../agent-rules/OWNER.md#usl-workspace-linking)에 따라
갱신 승인과 bounded reachability 전에는 실행하지 않았다. 이후 사용자 진행 지시로 수행한 실행은 아래에 기록한다.

## 검증

관련 5개 파일 **39개 테스트 통과**. 새 검사는 유한 묶음 의미 변화, 역할/예외/판본 누락, 자연어 UNKNOWN,
실행 피드백과 수치 갱신, 원자적 채택·새 프로세스·복원과 native RDF readback을 다룬다.
연구 입력 `--check`는 48개 할당을 독립 기대값과 대조했다. 실제 모델 응답 대신 테스트 transport를 쓴 검증이다.
추가 wire 변조·prompt 예산·부족한 관측·holdout 거부 검사는 같은 통합 경로에서 실행한다.
최종 TypeScript·Effect 경계·함수형 검사와 build도 통과했다. 전체 실행기 리허설은 **두 반복·116회 scripted 실행**을
완료했다. 각 반복에서 정책 revision 0→8, 구조 변경과 reset 9, 재학습 17을 영속화하고 별도 프로세스가 17을 사용했다.
provider 호출은 0회이며, 이 수치는 실제 LLM 효능이 아닌 실행 연결의 검증이다.

```bash
cd src/hswm/effect-runtime
npm run check
npm run build
npm test -- ../../../tests/effect-runtime/semantic-context-topology.test.ts \
  ../../../tests/effect-runtime/semantic-context-activation.test.ts \
  ../../../tests/effect-runtime/semantic-context-finite.test.ts \
  ../../../tests/effect-runtime/semantic-context-policy.test.ts \
  ../../../tests/effect-runtime/semantic-context.test.ts --maxWorkers=1
```

공용 호스트에서는 위 작업을 기존 managed scratch 한도 안에서 수행한다.
형식·로컬 연결 통과를 P00–P07 전체 완료나 실모델 개선으로 표시하지 않는다.

## 실제 실행과 HSWM_LIKENESS 연결 확인

후속 사용자 진행 지시를 앞서 제시한 범위의 갱신 승인으로 기록하고, 한 번의 bounded read-only
도달성 확인을 통과한 뒤 **동결된 protocol 그대로** 실행했다. 최초 등록 만료 기록은 당시 상태로 남긴다.
현재 실패는 접근 실패가 아니라 모델의 규칙 실행 충실도 실패다. 원격 서비스 설정은 변경하지 않았다.

### P01: 올바른 규칙을 보냈으나 모델이 반전을 실행하지 않음

2026-10-19 08:47 UTC, 실제 추론 **5회**, 공급자 보고 **25,524 tokens**, HTTP 시간 합계 약 **8.156초**다.
예정된 첫 개발 8개 중 처음 5개만 실행했다. identity의 두 bit·두 예외 상태 4개는 맞았지만,
다음 complement/bit=0/invalid=0에서 유일한 허용 출력 `1` 대신 `0`을 반환했다.
finish reason은 모두 `stop`이며 이 관측에서 토큰 상한 도달로 분류할 근거는 없다.

`check.mjs`는 실행기의 정답 함수를 import하지 않고 저장된 모든 유한 제약을 별도로 계산했다.
정확한 원문·역할·owner·예외와 canonical frame, 생성 prompt, 실제 HTTP body, 원본 응답,
trace 및 사후 정답을 대조했다. 실패 입력에는 mandatory와 complement만 전달됐고,
두 제약을 함께 만족하는 출력은 `1` 하나였다. 잘못된 후보 선택이나 trace 바꿔치기는 발견하지 않았다.
이 결과만으로 모델 내부의 실패 원인이나 표현 요소별 인과 효과를 특정하지 않는다.

사전 기준 `devViolations=0`에 따라 **P01_FAILED**로 중단했다. 나머지 개발, B0–B3, train,
재학습·topology 채택·실모델 재시작 실행은 모두 미실행이다. native journal은 state revision 2,
초기 W는 revision 0, 각 arm의 관측 수 0·A=I·b=0이다. 비교 성능은 null이며 4/5를 전체 실험
성공률로 쓰지 않는다. 최초 리허설의 revision 17은 scripted 검증이며 이번 실모델 결과와 별개다.

이전 10월 18일의 4/4 전달 진단과 달리 이번에는 정형 AST 제약과 전체 canonical JSON을 전달했다.
같은 `execution-tail` 명칭이 같은 입력·과제라는 뜻은 아니다. 기존 성공을 이 표현의 충실도로
대체하지 않는다. 다음 P01 작업은 **제약 전체의 의미를 보존하는 읽기 쉬운 표현을 새 개발 실험으로
검증**하는 것이다. 이전 실패 입력은 노출된 개발 자료로 남기고, 전달 방식이 검증되기 전에는
구조 후보를 늘리거나 새 W 개선 비교를 시작하지 않는다. 이번 cohort는 재시작하지 않는다.

### HSWM_LIKENESS는 어디에 연결되는가

| 연결 | 현재 실행 경로 | 이번 확인 |
|---|---|---|
| 연구 흡수 | likeness의 유한 의미·역할·예외 보존 연구 → HSWM finite 검사·topology retirement | [기존 흡수 기록](HSWM_LIKENESS_RESEARCH_TRANSFER_2026-10-18.md); sibling 계산기를 매번 호출하는 구조는 아님 |
| 외부 W 평가·정책 전달 | HSWM native binding → 실제 `hswm-likeness w context-policy` → owner admission → 다음 프로세스 | 현재 코드의 합성 교차 실행 PASS |
| 이번 온라인 W 학습 | HSWM trace/outcome → 자체 LinUCB → owner revision | 로컬 통합 검증 완료, 이번 실모델은 P01에서 중단 |

교차 실행은 exact source **20개**, 합성 **64 train + 320 holdout**을 실제 likeness CLI로 검사·계산했다.
`calendar` baseline → `door` revision 1 → 별도 프로세스에서 `door` 재읽기 →
revision 2로 `calendar` 복원을 확인했다. 모의 모델 호출 2회, 실제 provider 호출 0회다.
따라서 **실행 가능한 연결은 있으며, 이번 온라인 로그가 likeness 평가기로 자동 왕복하는 연결은 없다.**
현재 LinUCB의 적응형 기록을 likeness v1의 고정 무작위 IPS 입력으로 바꾸어 넣으면 평가 전제가 달라진다.
향후 직접 평가에는 적격한 고정 집단을 별도로 수집하거나 적응형 추정기 계약이 필요하다.

실제 인터페이스는 [정책 연결 문서](HSWM_CONTEXT_POLICY_BRIDGE_2026-10-11.md)와
[likeness 소유 사용법](../../../HSWM_LIKENESS/docs/CONTEXT_POLICY_BRIDGE.md)을 따른다.
첫 교차 실행은 검증 PASS 뒤 NFS로 hardlink를 복사하는 보존 단계에서 실패했다.
그 실패를 남기고 같은 로컬 검증을 다시 수행해 tar archive로 보존했다. 두 번째는 전체 명령 exit 0이며,
현재 재검사는 완전하게 보존된 두 번째 자료를 사용한다. 실모델 실패 cohort를 재실행한 것이 아니다.

### 원본과 재검사

private root는 `.hswm-local/semantic-w-loop-2026-10-19/`다. 원본 실행·정책 저장소와 별도 교차 실행
자료는 이 안에 보존한다. [내용 주소형 receipt](../../evidence/hswm_semantic_w_loop_2026-10-19/)가
private artifact manifest, source pin, 결과와 PROV-O source-bound graph snapshot을 묶는다.
reader는 아래 checker이며 원본 없음을 `NOT_HYDRATED`, 바뀐 원본·코드를 drift로 거부한다.
공유 KG 게시·운영 정책 변경은 하지 않았다. 이 기록은 agent(codex)의 측정 해석이며 정본 승격이 아니다.

원본 155개 대조, 성공 응답 위조·원본 누락 거부, PROV 24 triples의 국소 SHACL 조건과
SPARQL 결과 조회, provenance 활동 삭제 거부를 확인했다. 이는 해당 결과 연결의 검사이며
전체 PROV 제약·원격 관측의 진실성 인증이 아니다. 변경 Markdown도 portable 검사에 통과했다.

```bash
node _research/semantic_w_loop_v1/check.mjs \
  .hswm-local/semantic-w-loop-2026-10-19 \
  evidence/hswm_semantic_w_loop_2026-10-19/*.json
# HSWM_LIKENESS에서, 두 저장소가 build된 상태. archive는 managed artifact에 보존한다.
proxmox-scratch run likeness-hswm-bridge --timeout 600 --max-bytes 67108864 --memory-bytes 67108864 -- \
  bash -ec 'retained="$STORAGE_ARTIFACT_DIR"; export STORAGE_ARTIFACT_DIR="$STORAGE_MEMORY_TMPDIR"; \
  node tools/context-policy/verify.mjs ../HSWM; \
  tar -cf "$retained/context-policy-witness.tar" -C "$STORAGE_ARTIFACT_DIR" context-policy-witness'
```
