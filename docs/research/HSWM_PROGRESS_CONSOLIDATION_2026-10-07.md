# HSWM 작업·근거·남은 의무의 통합 그래프

2026-10-07 · `SECONDARY_AI_SOURCE_BOUND_REVIEW`

기존 [작업 계획](HSWM_STANDARD_GRAPH_PROGRESS_PLAN_2026-10-06.md),
[journal replay](HSWM_JOURNAL_REPLAY_2026-10-06.md),
[journal adapter](HSWM_JOURNAL_ADAPTER_2026-10-06.md)를 하나의 조회 문맥으로 연결했다.
T1~T9 각각의 현재 선택, T1의 세 관측, 근거의 역할·버전·검사 범위, 여섯 PS 의무와
다음 작업을 같은 그래프에서 조회한다. 이전 snapshot의 내용과 해시는 보존한다.

검토한 코드 기준은 `b29cb8268b6f9e110739e40989f5bdf7ba8d3739`다.
이 기준에서 journal adapter는 부분 보존·재구성 증명이며 T1 전체는 `OPEN`이다.
이후 workspace의 미커밋 변경, 현재 모델 endpoint, 새로운 실험 결과는 이 판정에
포함하지 않는다. 이번 통합은 새 Lean 정리나 모델 실험의 실행 기록이 아니다.

## HSWM 계약에 맞춘 구성

HSWM의 canonical graph는 AI의 상태이고 국소 LLM은 그 상태를 입력받는 계산 주체다.
TS/Effect는 버전이 정해진 해석기와 I/O를 담당한다. 이번 저장소 그래프는 **그 프로그램의
증명·근거·작업 의무를 조회하는 연구 view**다. canonical 학습 상태나 승인 경로로 사용하지 않는다.
고정 `H/W/A/F/Π` 분해를 다시 도입하지 않는다.

작업 순서를 TypeScript 분기문에 추가하지 않고 기존 task UID와 `REQUIRES` 관계를 읽는다.
관측은 task의 정체성과 구별하고, selector가 지정한 관측 하나를 현재 조회 대상으로 삼는다.
필요한 출처만 task별로 연결한다. 예를 들어 T1에는 adapter의 직접 근거 13개를 연결하고,
T2의 Permit 코드 열람 4개는 `INSPECTION_ONLY`로 표시해 T1 실행 증거로 세지 않는다.
원문과 원본 바이트로 돌아가는 경로를 유지하며, 통합 성공을 의미 학습의 인과 기여로 평가하지 않는다.

기존 bundle v2와 RDF 1.1·SHACL 1.0·SPARQL 1.1·PROV-O 구현을 그대로 사용한다.
새 데이터베이스, graph engine, canonical 쓰기 API나 승인 절차를 만들지 않았다.
관계의 identity·scope·authority·status를 유지하는 기존 RDF 재화 표현도 보존한다.
이 view는 native atom payload·역할 순서·원본 schema를 대체하지 않는다.

## 네 출처를 함께 읽는 경계

[통합 bundle](../../ontology/development/HSWM_PROGRESS_CONSOLIDATION_2026-10-07.v1.json)은 새 관측과
선택만 소유한다. 기존 세 bundle의 task·claim·decision을 복제하거나 UID를 재정의하지 않는다.
원래 owner가 네 출처 dataset에 함께 들어와 anchor를 해소한다.

[workspace manifest](../../ontology/workspace/HSWM_WORKSPACE.v1.json)의 `progress` entry는
세 `additional_sources`의 경로·ID·SHA-256을 명시한다. query/validate는 그 bytes가 달라지면
실행을 거절한다. 같은 node UID를 서로 다른 bundle이 소유하는 경우도 거절한다.
primary 통합 bundle은 실행 시 관측한 현재 bytes이며 `CURRENT_OBSERVED`, 추가 세 bundle은
`MANIFEST_PINNED`다. 응답의 `selectedSources`로 실제 읽은 네 출처를 확인할 수 있다.
primary bytes를 manifest hash로 고정했다고 주장하지 않는다.

기존 단일 bundle entry도 같은 명령으로 동작한다. `show`와 `bindings`는 primary 범위이고,
추가 bundle 내부의 역사적 artifact를 재검증하는 명령은 아니다. 역사적 바이트 재현은 아래
명시적 Git 검사로 수행한다. `query`는 조회이고, `validate`가 선언된 SHACL 구조를 검사한다.

## 상태·역사·증거의 의미

| 구성 | 의미와 검사 |
| --- | --- |
| `PROGRESS_VIEW` | 조회 기준 revision과 날짜, 선택 규칙, 전체 증명/효능 비주장. |
| `CURRENT_SELECTION` | 기존 task 하나에 대해 관측 하나를 명시적으로 선택한다. T1~T9 각각 정확히 하나. |
| `TASK_STATUS_OBSERVATION` | task·원본 관측·source revision·순서·이전 관측·다음 작업을 함께 기록한다. 전체 완료는 별도 `OPEN`. |
| `SOURCE_BINDING_OBSERVATION` | 동일 경로라도 bundle/bytes/revision이 다르면 별개 출처 발생으로 보존한다. |
| 기존 Claim/Decision | PS-1~6과 부분 증명의 기존 판정·한계를 재사용한다. 새 selector는 그 판정을 승격하지 않는다. |
| `EVIDENCE_ARTIFACT` | 이전 검증 보고서 3개. 이번에 그 테스트·정리를 다시 실행했다는 의미가 아니다. |

새 역할은 위 versioned bundle의 로컬 연구 어휘이며 canonical atom 종류가 아니다.
label은 기존 `AbstractNode`, 관계는 기존 `HAS_CONCEPT`, `HAS_SOURCE`, `REFERENCES`를 사용한다.
`REQUIRES`는 원래 task DAG에만 남긴다. 관측의 이전 관계는 `previous_observation_uid`와
범위가 명시된 `REFERENCES`로 나타내며 authority 승계나 인과 관계를 뜻하지 않는다.

선택과 관측은 각각 검토 revision과 `AT_REVIEWED_GIT_REVISION_NOT_LIVE_WORKTREE` 범위를 가진다.
T1은 `NEXT → PARTIAL_BOUNDARY_PROVED_REFINEMENT_OPEN → PARTIAL_PRODUCER_PROVED_REFINEMENT_OPEN`
세 관측을 보존하고 마지막을 선택한다. 날짜 문자열의 최대값으로 상태를 추측하지 않는다.
T2의 다음 작업은 native preflight와 세 Lean `adapterFacts`의 대응이다. T5는 과거의
`PREPARED_NOT_RUN` 관측을 보존하며 현재 serving 준비나 실제 요청 실행을 확인했다고 하지 않는다.

근거 발생 39개 중 검토 revision의 bytes와 일치하는 것은 35개다. 나머지 4개는 plan의
journal 파일 1개, replay의 journal·lakefile·proof-process 파일 3개다. **39개 모두 각
snapshot이 커밋된 revision에서는 원래 해시와 일치한다.** `HISTORICAL_PIN_DRIFT`는 이
정상적인 역사적 차이를 나타낸다. `CURRENT_MATCH`도 지정된 검토 revision과의 일치이지
이후 모든 worktree에 대한 보장이 아니다. 옛 해시를 현재 해시로 덮어쓰지 않는다.

## 질문과 반복 가능한 검사

저장소 루트에서 실행한다. source별 파일 경로를 매번 다시 조합할 필요가 없다.

```sh
src/hswm/effect-runtime/bin/hswm-workspace show progress
src/hswm/effect-runtime/bin/hswm-workspace validate progress
src/hswm/effect-runtime/bin/hswm-workspace query progress current
src/hswm/effect-runtime/bin/hswm-workspace query progress history
src/hswm/effect-runtime/bin/hswm-workspace query progress bindings
src/hswm/effect-runtime/bin/hswm-workspace query progress evidence
src/hswm/effect-runtime/bin/hswm-workspace query progress next
src/hswm/effect-runtime/bin/hswm-workspace query progress boundaries
```

[질의와 shape](../../ontology/queries/hswm_progress_consolidation_2026-10-07/README.md),
[고정 입력 계약](artifacts/hswm_progress_consolidation_2026-10-07/contract.v1.json),
[검증 결과](artifacts/hswm_progress_consolidation_2026-10-07/validation.v1.json)를 함께 보존한다.
검사는 행 수 외에 정확한 task·status·완료 기준·의존 관계·source hash·효능 판정을 대조한다.
SHACL Core가 다루지 않는 selector UID/edge 일치와 관측 순서의 일관성은 별도 회귀 검사로 확인한다.
출처 ID는 원본 bundle UID·revision·artifact hash와 함께 대조한다. `history`는 이 snapshot의
선택 관측에서 UID와 edge가 일치하는 두 이전 관측만 따라간다. 이력 길이를 늘릴 때는
새 snapshot의 질의·검사도 함께 갱신한다.
Claim↔Decision의 정상 순환을 금지하지 않으며 task 의존성과 관측 이력의 순환만 검사한다.

```sh
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime run build
HSWM_VERIFY_PROGRESS_HISTORY=1 npm --prefix src/hswm/effect-runtime test -- ../../../tests/effect-runtime/progress-consolidation.test.ts test/workspace-composite.test.ts --maxWorkers=1
```

역사 재현에는 계약에 적힌 세 Git revision이 필요하다. 환경변수 없는 기본 테스트에서는
그 항목이 명시적으로 skipped로 표시된다. 이번 기록에서는 변수를 켜고 실제 Git 바이트를
읽었다. source cut을 바꾸려면 새로운 snapshot·검증 기록을 만들고 workspace의 명시적 선택을
갱신한다. 누락된 선행 관측을 완료로 취급하지 않는다.

## 차근차근 이어갈 작업

`next`는 T1과 T2의 한정된 구현 작업만 반환한다. 이 값은 실행 권한이나 원격 작업 승인이 아니다.
우선 T2의 native preflight 성공→`permitEnvelopeAccepted`, `stateBytesAccepted`,
`verificationTimeAccepted` 대응을 구성하고, T1의 strict decoder/native validator 의무를
이어간다. T4는 T1·T2·T3의 완료 근거가 없으면 열리지 않는다. 학습 효능은 실제 W1~W5
대조 실험의 별도 의무이며 기존 부정 결과와 PS-3·5·6의 미확립 판정을 유지한다.
