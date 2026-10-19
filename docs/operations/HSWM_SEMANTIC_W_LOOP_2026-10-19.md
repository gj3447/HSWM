# 의미 보존 구조 변경과 W 재결속 — 첫 실행 범위

2026-10-19 · agent(codex) 구현·검증 기록. [작업 계획](HSWM_SEMANTIC_W_OPTIMIZATION_PLAN_2026-10-18.md)의 후속이며,
동결된 계획과 이전 실험 수치를 수정하지 않는다.

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
| P00 | 첫 유한 퇴역 실험의 실행기·고정 입력·판정·호출 상한 준비 | 현재 원격 등록 갱신과 fresh reachability |
| P01 | CLI의 명시적 실행 전달·prompt/wire 결속 구현, 테스트 | 새 유한 규칙의 실모델 실행 충실도 |
| P02 | 기존 결과 기반 학습 재사용, 새 trace로 학습·중복 거부 검사 | 새 실모델 cohort와 수치 근접 동점 재현성 |
| P03 | 전체 유한 묶음·역할·예외 보존 검사 | 임의 자연어 추상화, 새 분해/허브 의미 검증 |
| P04 | 지원된 묶음의 제한된 중복 연결 퇴역 후보 | 허브 생성·분할·병합 proposer와 조합 기여 평가 |
| P05 | 구조·reset W 동시 owner 채택 검사 | 실모델 실행과 동일한 연구 저장소에서의 채택 |
| P06 | 별도 OS 프로세스 실행, 중복 거부, append-only 복원 검사 | 실모델 후속 실행 |
| P07 | 사전 고정 2×2 비교 실행기 준비 | 실제 cohort와 비용·실패·불확실성 보고 |

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

기존 등록은 **2026-10-19 00:00 UTC에 만료**됐다. 이번 작업의 새 모델 호출은 **0회**이며,
원격 경로 상태는 `NOT_READY`다. [OWNER의 USL workspace linking](../agent-rules/OWNER.md#usl-workspace-linking)에 따라
갱신된 범위 승인과 bounded reachability 전에는 실행하지 않는다. 로컬 구현·일반 테스트는 계속 진행했다.

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
