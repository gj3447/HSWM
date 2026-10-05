# 의미 실행의 Step/Learn 연결과 반복 라운드 합성

2026-10-05 · `SECONDARY_AI_CONDITIONAL_FORMAL_RESULT`

기존에 검사하던 실제 semantic lifecycle 기록을 공통 `Dynamics`의 구체적인
Step/Learn 실행으로 연결했다. 한 번의 수락된 기록뿐 아니라, **선택된 상태가 다음
라운드의 시작 상태와 정확히 일치하는 모든 유한 기록열**에서 출력·최종 상태와
소유자·역할 순서·예외 순서가 보존됨을 Lean 4로 증명했다.

이는 [P1–P5 계획](../operations/HSWM_WHOLE_SYSTEM_LEAN_TARGETS_2026-09-28.md)의
P1과 반복 라운드의 구조 연결을 진전시킨다. P3의 확률적 선택 보장이나 실제 학습
효능을 완료 처리하지 않는다. 기존 CR-0…7/FCL-1…8의 전체 판정도 유지한다.

## 정의와 증명 범위

[새 모듈](../../formal/HSWMSemanticOperationalBridge.lean)은 기존
`HSWMSemanticLifecycleRefinement`와 `HSWMSemanticQuotient`를 사용한다.

- 상태는 `StateView`: 선택된 관계의 키·소유자·의미·역할 및 전역 revision이다.
- Step 입력은 실제 기록에서 복원한 frame과 trace다. 정확한 상태·frame·trace
  연결이 맞으면 해당 trace를 출력하고 관계 상태는 유지한다.
- Learn 입력은 frame·trace·outcome·revision과 관측된 선택 Boolean이다.
  연결 검사가 맞고 후보가 선택됐을 때 `semanticSuccessor`로 이동한다.
  기준 상태가 선택된 라운드는 Learn이 거절된 채 상태를 유지한다.
- 라운드는 training Step → 선택된 Learn 또는 거절 → next Step이다.
  이전 라운드의 선택 상태와 다음 라운드의 `before`가 다르면 연결을 거절한다.

| 정리 | 보장 |
| --- | --- |
| `accepted_training_read`, `accepted_next_read` | 수락된 기록의 두 읽기가 같은 상태 정의에서 허용된다. |
| `accepted_learning_bound`, `accepted_learning_guard` | outcome·revision 연결이 맞고 Learn 허용값은 실제 선택 Boolean과 같다. |
| `accepted_learning_advance`, `accepted_round_replays` | 한 라운드가 공통 Step/Learn 의미론에서 정확한 출력과 선택 상태로 재현된다. |
| `accepted_chain_replays` | 연결된 모든 유한 라운드의 출력열과 최종 상태가 재현된다. |
| `accepted_selected_invariants`, `accepted_chain_preserves_invariants` | 소유자·역할 순서·예외 순서가 라운드 전체에서 보존된다. |
| `accepted_selected_revision`, `accepted_chain_revision_count` | revision 증가량은 실제 선택된 후보의 개수다. 거절된 후보는 증가량에 포함되지 않는다. |
| `stale_round_rejected`, `empty_chain_not_evidence` | 시작 상태가 다른 라운드와 빈 기록열을 근거로 인정하지 않는다. |

보조 정리 `run_append`를 포함해 새 정리 14개다. 기존 사후 검사와 같은 전제를
재사용한다. 수락됐다는 조건을 공리로 추가하거나 `sorry`로 남긴 명제는 없다.
소스·공리 검사는 [새 프로파일 보고서](../../_research/semantic_operational_chain_2026-10-05/lean-verification.v1.json)에 있다.

## 실제 실행 연결

기존 [Lean CLI](../../formal/HSWMSemanticLifecycleCli.lean)에
`hswm-semantic-lifecycle-chain/v1`을 추가했다. 기존 단일 기록 입력·출력은 그대로다.
새 입력은 `contract`와 `rounds` 배열이며, 기존 decoder와 사후 checker로 모든 라운드를
검사한 뒤 정확한 상태 연결도 확인한다. 빈 배열의 `accepted`는 `false`다.

[순수 TS 조립 함수](../../src/hswm/effect-runtime/src/semantic-lifecycle-chain.ts)는
`projectSemanticLifecycleRefinement`로 얻은 기록 1–1000개를 복사·동결하고 상태 연결을
확인한다. 이 함수의 성공은 개별 기록의 Lean 수락을 뜻하지 않는다. 각 기록의
바이트·내부 연결은 기존 Effect adapter와 Lean checker가 각각 담당한다.

[통합 테스트](../../tests/effect-runtime/semantic-lifecycle-chain.test.ts)는 실제 파일 저장소,
내용에 결속된 revision, graph-loop admission, 고정된 선택 입력, 새 runtime 재개방을
사용한다. `[후보, 기준, 후보]`와 `[기준, 후보, 기준]` 두 3라운드 기록열을 검사했다.
각 라운드의 사후 검사를 먼저 통과시키고 전체 기록열도 검사한다.

라운드 순서 변경·오래된 라운드 삽입·중간 상태 변경·outcome 변경·선택 반전·예외 삭제·
빈 기록열의 7종 × 2개 기록열, 총 14건이 거절됐다. 이 반례의 거절은 모든 가능한
replay 공격이나 불완전한 기록의 탐지를 증명하지 않는다. 특히 상태를 바꾸지 않는
유효한 라운드의 반복을 일반적으로 금지하는 계약은 아니다.

[실행 관측](../../_research/semantic_operational_chain_2026-10-05/runtime-verification.v1.json)은
두 기록열의 전체 normalized wire와 실행한 checker binary hash를 보존한다.
HTTP 응답과 선택 정답은 작성된 fixture다. 실제 모델 호출은 0회다.

```bash
(cd formal && lake build HSWMSemanticLifecycleCli)
npm --prefix src/hswm/effect-runtime run build
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile semantic-operational --output .local/semantic-operational-proof
HSWM_RUN_SEMANTIC_LEAN=1 npm --prefix src/hswm/effect-runtime run test -- ../../../tests/effect-runtime/semantic-lifecycle-chain.test.ts ../../../tests/effect-runtime/semantic-lifecycle-refinement.test.ts --maxWorkers=1
```

감사기는 새 출력 디렉터리에서 import closure를 컴파일하고 `--trust=0`과 정리별
`#print axioms`로 다시 검사한다. 공개 보고서는 로컬 실행 경로를 제거한 파생본이며,
원본 보고서의 SHA-256과 소스·컴파일러·공리 기록을 유지한다.

## 아직 남은 핵심

이 모델의 trace는 외부에서 공급된 실제 관측 입력이다. 모델이 LLM 응답을 생성하거나
예측했다는 정리가 아니다. 선택 Boolean도 기존 실행에서 관측한 값이므로 효용의
정당화, 독립 표본, 오류 예산, heldout 미재사용은 별도로 확인해야 한다.

연결 검사는 **선택된 관계 view**를 비교한다. 전체 저장소·외부 세계·파일시스템 crash·
TypeScript/JSON/SHA 구현의 정제 증명이나 wall-clock 인과 순서를 포괄하지 않는다.
전역 revision을 제거한 국소 읽기로 같은 Learn guard를 보존할 수 있다는 보장도 없다.

다음 실험은 후보 생성 이력과 평가 split을 사전에 고정하고, frozen/evidence-only/
sham/learned를 같은 시작 상태·실제 모델·비용 한도에서 비교해야 한다. 매 라운드의
독립 결과를 이 기록열과 연결하되 실패·no-op·기준 상태 선택도 포함해야 한다.
[기존 음성 결과](../../results/HSWM_DGX_SEMANTIC_LEARNING_2026-09-20.md)를 이번 구조
증명으로 대체하지 않는다. 학습 효능·전체 HSWM·metahumotonic 완성은 계속 미입증이다.

[연구 연결 snapshot](../../ontology/development/HSWM_SEMANTIC_OPERATIONAL_CHAIN_2026-10-05.v1.json)은
정리·실행 관측·한계를 연결한 로컬 SECONDARY_AI 자료다. live KG 변경이나 canon 승격은 없다.

## 넓힌 회귀 검사에서 확인한 별도 문제

전체 runtime 검사는 1,524개 통과, 2개 실패, 32개 생략과 한 suite 초기화 실패를
보고했다. 따라서 전체 suite 성공으로 기록하지 않는다.
실패 원인은 [기준 소스·환경 대조](../../_research/semantic_operational_chain_2026-10-05/baseline-check-findings.v1.json)에 남겼다.

- 기존 `seedSemanticLifecycle`의 직접 `runtime.submit` 호출과 “src 전체에 직접 호출이
  없어야 한다”는 경계 테스트의 불일치. 해당 구현과 테스트는 기준 commit의 바이트와 같다.
- drand suite가 고정한 Node 실행파일 SHA-256과 현재 Node v24.20.0의 불일치.
  검토된 pin을 현재 실행파일에 맞춰 바꾸지 않았다.
- 9월 22일부터 남아 있던 빈 임시 빌드 디렉터리가 소스 검사 테스트의 전역 빈 목록
  검사를 실패시켰다. 디렉터리를 로컬에 보존하여 작업 디렉터리 밖으로 옮겼다.

이 검사는 새 정리의 커널 성공과 구별한다. 특히 fixture의 bootstrap은 정리 밖의
adapter 전제이며, 전체 production admission 경계가 증명됐다고 해석할 수 없다.
