# 전체 HSWM 구현으로 이어지는 첫 Lean 증명 라운드

2026-09-28 · `SECONDARY_AI_BOUNDED_FORMAL_RESULT`

[공략 순서](../operations/HSWM_WHOLE_SYSTEM_LEAN_TARGETS_2026-09-28.md)의 P1에서 시작해,
실제 의미 실행 기록의 구조적 대응과 P2·P3의 기초 정리를 구현했다.
[큰 그래프가 AI 상태이며 LLM은 국소 연산자](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md),
[M은 층간 Map](../canon/USER_PRIMARY_HSWM_CROSS_LAYER_MAP_2026-09-27.md),
[HSWM은 더 넓은 CHU의 LLM 계산 대상](../canon/USER_PRIMARY_CHU_HSWM_SOFTWARE_SCOPE_2026-09-27.md)이라는
사용자 방향을 유지한다. 이번 정리에서 하이퍼그래프의 보편 최소 비용이나 우주 전체의 계산가능성을 전제하지 않는다.

## P1: 저장된 의미 수정과 다음 읽기를 연결

[HSWMSemanticLifecycleRefinement](../../formal/HSWMSemanticLifecycleRefinement.lean)는
현재 TS의 문자열 schema/lineage/UID, revision, owner, 순서 있는 역할, 의미 텍스트·불확실성·예외와
trace/outcome/revision-evidence 참조를 옮긴 모형이다. 예전 고정 세 역할의 Nat 모형에
실제 frame을 이미 연결했다고 가정하지 않는다.

`postRunAccepted`는 실행 가능한 순수 검사 함수다. `semanticSuccessor`는 이전 관계와
수정 응답에서 다음 관계를 구성한다. 다음 정리는 임의의 decoded wire에 적용된다.

- `accepted_after_eq_semanticSuccessor`: 검사 성공이면 기록된 after 상태는 이전 상태와
  수정 응답으로 구성한 정확한 successor다. schema·lineage·UID·owner·역할·예외가 보존되고
  관계 revision과 state revision은 1 증가하며, 내용과 evidence는 해당 수정 응답에 결속된다.
- `accepted_projects_next_trace_reads_selected_state`: 다음으로 보고된 실행의 relation key는
  선택한 후보 또는 baseline의 정확한 key다. frame의 의미 payload와 역할도 함께 검사한다.
- `accepted_retains_exact_predecessor`: supersedes 대상과 보존된 이전 관계가 일치한다.
- 역할·예외 보존 및 다른 trace를 붙인 outcome의 거절 정리도 포함한다.

[TS/Effect adapter](../../src/hswm/effect-runtime/src/semantic-lifecycle-refinement.ts)는 실제 durable
저장소에서 prediction 요청·응답, trace, outcome, revision 요청·응답·evidence, 보존된 이전 atom,
현재 후보와 선택된 실행의 요청 frame을 읽는다. byte length·SHA-256·JSON shape를 확인하고,
요청 frame을 재구성한 실제 frame 전체와 비교한 뒤 Lean 입력을 만든다.
[Lean CLI](../../formal/HSWMSemanticLifecycleCli.lean)는 그 입력에 증명한 함수를 실행한다.
학습 admission 경로를 추가하거나 변경하지 않는 사후 검사다.

현재 semantic lifecycle은 graph-loop admission을 사용한다. 기존 `VerifiedAdmissionKernel/Wire`
정리는 별도의 LocalPermitCommit 모형이므로 이 증명에 자동 합성하지 않았다. 이전 계획의
"기존 admission 재사용"은 실제 호출 경로 확인 뒤 이 구분으로 구체화했다.

**증명의 정확한 경계:** Lean이 검사하는 것은 decoded projection이다. JSON parser, SHA 구현,
TS 전체 프로그램, OS·crash 복구, LLM 응답의 의미와 outcome의 진위는 Lean으로 증명하지 않았다.
adapter의 실제 byte 연결은 통합 검사로 확인한다. normalized wire는 descriptor 세부,
역할 본문, prior-evidence의 확장 내용을 모두 담지 않으므로 full-request refinement라고 부르지 않는다.
또한 선택 기록과 실행 기록의 일치는 selection이 heldout보다 먼저 일어났다는 시간 순서 증명이 아니다.
보고서에 `chronologyVerified: false`를 기록하고, 실행 파일 hash도 compiler correctness와 구별한다.

## P2: 선택한 참조 집합 밖의 변경은 국소 읽기에 영향을 주지 않는다

[HSWMSemanticReadLocality](../../formal/HSWMSemanticReadLocality.lean)는 P1의 실제 문자열·key 타입을 재사용한다.
저장소를 exact key에서 본문으로 가는 부분 함수로 두고, `resolveRoles`가 관계의 역할 목록을
순서대로 읽는다. `readPlan_locality`는 다음 조건에서 두 읽기 결과가 같음을 리스트 귀납법으로 증명한다.

- 선택 관계와 task event가 같다.
- 그 관계가 참조하는 모든 pinned key에서 두 저장소의 key·owner·content hash·본문이 같다.

그 밖의 그래프 값은 달라도 된다. 역할 본문이 없거나 명시된 예외로 가는 exception-role 경로가
없으면 읽기는 `none`이다. 예외 참조 삭제와 역할 순서 변경이 정보를 잃는 반례도 유지한다.

이 결과는 read-plan 구성요소의 locality다. 전역 state revision과 frame hash,
확장된 과거 trace/outcome, prompt wrapper까지 동일하다는 결과가 아니다. 실제 task에서 충분한
읽기를 발견하는 planner, 추가 읽기·abstention, Step뿐 아니라 Learn까지의 `FibreCriterion`
인스턴스는 후속 구현·증명 대상이다. 같은 입력이면 모든 실제 LLM 응답이 같다고 가정하지 않는다.

## P3: 과거 이력마다 달라지는 후보에 fresh 평가 정리 적용

[AdaptiveRounds](../../formal/statistical-learning/HSWMStatisticalLearning/AdaptiveRounds.lean)는
기존 [frozen-round 통계 정리](HSWM_FRESH_EVALUATION_LEAN_PROOF_2026-09-28.md)를 실제 호출한다.

`kernelwise_statistical_selection_failure_le_delta`는 유한 과거 이력 각각에 대해 별도의 fresh
평가 확률법칙을 둔다. 후보는 그 이력으로 정하지만 새 표본의 함수로 두지 않는다.
각 법칙에서 독립 bounded 행, 기대값, 최대 교체 행 witness 등 기존 조건으로 실패 상계를 도출한다.
후보끼리의 독립성이나 서로 다른 라운드 사이의 독립성은 추가하지 않는다.

`kernelwise_statistical_selection_mixture_failure_le_delta`는 비음수 이력 가중치의 합이 1인
유한 혼합 실패량도 같은 δ 이하임을 보인다. 여기서 실패는 기존 `RoundWorks`의 부정이므로
잘못된 채택과 충분한 margin이 있는데 선택하지 못하는 경우를 함께 다룬다.

`history_conditional_failure_le`는 가측·서로소·전체를 덮는 유한 이력 partition의 조건부 실패량을
전체 실패확률로 연결한다. `finite_alpha_spending_failure_le`와
`stopped_failure_le_alpha_spending`는 이미 제어된 유한 라운드들의 실패 합집합을 오류 예산의 합으로
제어하고, 실행한 라운드를 중단 정책으로 줄여도 그 상계가 유지됨을 보인다.

유한 혼합량을 실제 운영 transcript의 joint law로 식별하는 일, 조건부 freshness의 실제 보장,
무한 horizon·라운드 안의 데이터 의존 중단, 후보 발견, 비용과 TS 정수 guard의 수치 대응까지
증명한 것은 아니다. 최대 b개 행 교체와 Huber 분포 오염도 계속 구별한다.
[기존 문헌·원문 hash 지도](../operations/artifacts/hswm_whole_system_lean_targets_2026-09-28/source-map.v1.json)의
Learn then Test·confidence sequence를 이런 후속 의무에 사용한다.

## 검증과 재현

기존 TS/Effect proof auditor에 `semantic-lifecycle` profile과 `AdaptiveRounds`를 추가했다.
새 정리·보조정리 26개(P1 12·P2 7·P3 7)와 기존 통계 정리 37개의 공리 검사를 통과했다.
새 OLean 디렉터리에서 다시 컴파일하고 정리별 공리를 조사한다. `sorry`, 사용자 axiom,
`native_decide`를 허용하지 않는다. Lean 표준 공리와 pinned Mathlib의 compiled imports는 신뢰 기반이다.
독립 compiler 검증이나 모든 dependency OLean의 source rebuild를 주장하지 않는다.

```sh
cd formal
lake build HSWMSemanticLifecycleCli HSWMSemanticLifecycleRefinement
cd ..
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile semantic-lifecycle --output .hswm-local/NEW_CORE_PROOF_RUN
node src/hswm/effect-runtime/dist/statistical-learning-proof-process.js --output .hswm-local/NEW_STATISTICAL_PROOF_RUN
HSWM_RUN_SEMANTIC_LEAN=1 npm --prefix src/hswm/effect-runtime run test -- ../../../tests/effect-runtime/semantic-lifecycle-refinement.test.ts
node src/hswm/effect-runtime/dist/semantic-lifecycle-refinement-process.js --root EXISTING_SELECTED_LIFECYCLE --output .hswm-local/NEW_POSTRUN_AUDIT
```

실제 파일 저장소와 scripted transport로 후보 선택과 baseline 선택을 각각 실행했다.
두 입력은 Lean CLI가 받아들이고, 각 입력의 event·trace·state revision·역할 순서·예외·수정 내용·
이전 owner·predecessor·선택 branch·backend·후속 event를 바꾼 22개 입력은 거절한다.
TS adapter의 prediction 바꿔치기와 content byte 손상도 거절한다. 새 실모델 호출은 없다.

[검증 기록](../../_research/whole_system_lean_round_v1/verification.v1.json)과
[출처 결속 KG](../../ontology/development/HSWM_WHOLE_SYSTEM_LEAN_ROUND_2026-09-28.v1.json)에
소스 hash, 실제 검사와 한계를 보존한다. 다음 순서는 P2의 실제 read planner와 P3의 평가 계약을
연결하고, 이어 P4의 구조 변경 consumer와 P5의 두 cell 공동 Step/Learn을 구현하는 것이다.
과거 음성 결과, CR-0..7/FCL-1..8, 정확한 버전의 Hyperon 필수 비교는 유지한다.
