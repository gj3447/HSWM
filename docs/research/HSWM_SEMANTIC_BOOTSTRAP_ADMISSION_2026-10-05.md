# Semantic lifecycle 초기화의 graph-loop 연결

2026-10-05 · `SECONDARY_AI_ENGINEERING_VALIDATION`

[이전 반복 라운드 검사](HSWM_SEMANTIC_OPERATIONAL_CHAIN_2026-10-05.md)에서 발견한
초기화의 직접 durable submit을 제거했다. 초기화도 trigger → action seal → mechanical
verification → delta intent → commit 경로를 거친다. 기존 atom·전이 내용은 유지하며
새 graph-loop 기록을 남긴다. 이는 구현 경계 수정이며 새 Lean 정리나 학습 효과 결과가 아니다.

## 변경과 제한

[컨트롤러](../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.ts)의
기존 `affectedKeys`는 이미 존재하는 match/read key를 뜻한다. 첫 상태에는 그런 key가
없으므로 빈 집합을 다음 조건에서만 허용한다.

- 캡처한 snapshot과 현재 canonical revision이 모두 0이다.
- 현재 canonical atom과 candidate read-set이 모두 비어 있다.
- candidate write는 비어 있지 않고, schema·content binding·reference grant 검사를 통과한다.
- 별도 actor/verifier ID, action seal, ACCEPT, evidence content와 fresh snapshot 검사를 통과한다.

이미 상태가 있는 저장소의 빈 match와 restore의 빈 source는 계속 거절한다.
같은 초기 snapshot에서 시작한 두 run 중 먼저 commit된 것만 적용되고 오래된 것은
`QUARANTINED`가 된다. 이 검사는 경쟁을 순서대로 재현한 사례이며 모든 동시 실행의 증명은 아니다.

[초기화](../../src/hswm/effect-runtime/src/semantic-lifecycle-runtime.ts)는 승인 오류를 전달하고,
`REJECTED`나 `QUARANTINED` 결과도 `BOOTSTRAP_NOT_COMMITTED` 오류로 처리한다.
성공 때는 기존처럼 durable evolution을 반환한다. 재초기화는 기존 run ID 때문에 거절된다.
실패 전에 staging한 content나 control 기록은 남을 수 있다. canonical 상태가 생성되지
않는다는 보장과 모든 파일 쓰기가 없다는 주장을 구별한다.

이 fixture의 verifier는 같은 로컬 프로그램의 기계적 검사 경로다. 서로 다른 ID가
독립된 의미 판단자를 보증하지 않는다. `REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT`,
`semanticCorrectness: NOT_ADJUDICATED`, `efficacy: NOT_ADJUDICATED`를 유지한다.

## 확인한 실행

- 새 bootstrap 7건과 controller genesis 2건을 포함한 관련 13개 파일, 총 46개 테스트 통과.
- 승인 4단계 오류 주입, REJECTED/QUARANTINED 응답, 재개방, 중복 초기화, 잘못된 genesis,
  빈 restore, 상태가 있는 곳의 빈 match, 오래된 genesis를 검사했다.
- 기존 원시 submit 경계 테스트를 수정하지 않고 통과했다.
- `HSWM_RUN_SEMANTIC_LEAN=1`로 실제 파일 저장소의 단일 라운드 및 두 3라운드 기록열을
  기존 Lean checker로 다시 검사했다. 기존 변조 거절 검사도 통과했다.
- TypeScript·Effect boundary·functional check와 build가 통과했다.
- 빌드된 별도 worker process를 사용하는 scripted CLI가 선택된 branch를 재개방하고
  heldout 단계까지 완료했다. HTTP 모델 요청은 0회이고 판정은 `SCRIPTED_WIRING_ONLY_NOT_MODEL_EFFICACY`다.

```bash
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime run build
HSWM_RUN_SEMANTIC_LEAN=1 npm --prefix src/hswm/effect-runtime run test -- ../../../tests/effect-runtime/semantic-lifecycle-bootstrap.test.ts ../../../tests/effect-runtime/semantic-lifecycle-chain.test.ts ../../../tests/effect-runtime/semantic-lifecycle-refinement.test.ts ../../../tests/effect-runtime/canonical-atom-v2-semantic-selected-state.test.ts test/canonical-atom-v2-graph-loop-enforcement-boundary.test.ts test/canonical-atom-v2-graph-loop-engineering.test.ts --maxWorkers=1
npm --prefix src/hswm/effect-runtime run test -- ../../../tests/effect-runtime/semantic-lifecycle-domain.test.ts ../../../tests/effect-runtime/semantic-lifecycle-runner.test.ts ../../../tests/effect-runtime/semantic-lifecycle-transport.test.ts ../../../tests/effect-runtime/semantic-lifecycle-selection.test.ts ../../../tests/effect-runtime/canonical-atom-v2-llm-semantic-runtime.test.ts test/canonical-atom-v2-graph-loop-research-job.test.ts test/canonical-atom-v2-routing-diagnostic-file.test.ts --maxWorkers=1
node src/hswm/effect-runtime/dist/semantic-lifecycle-process.js --output NEW_PRIVATE_DIRECTORY --transport scripted --allowance 0 --debit 0
```

전체 suite는 이번에 다시 실행하지 않았다. 이전 drand suite의 Node 실행파일 pin 불일치는
미해결이며 pin을 변경하지 않았다. 이전 실패 기록과 source hash는 그대로 보존한다.
새 controller 분기 전체를 Lean으로 정제한 것은 아니다.

## 이어서 할 핵심

1. **실행과 증명의 대응 범위 확대.** 현재 relation view 정리에서 전체 store·read-set·admission의
   어떤 정보를 보존해야 하는지 정의한다. 특히 국소 frame이 같아도 전역 revision이 바뀌면
   Learn의 CAS 승인이 달라질 수 있다. 이 반례를 보존하고 P2의 국소성 조건을 구체화한다.
2. **실제 학습 효과의 독립 평가.** 후보 생성 이력, model/config, 평가 split, 비용과 중단 규칙을
   평가 전에 고정한다. frozen/evidence-only/sham/learned를 같은 시작 상태와 예산에서 비교하고,
   평가 재사용을 막으며 실패·no-op·기준 상태 선택도 남긴다. 구조 증명은 과거 음성 결과를 지우지 않는다.
3. **구조 변경과 공동 학습.** 역할·예외·계보를 보존하는 구조 delta가 다음 실행을 실제로 바꾸는지,
   두 cell의 국소 수정이 공동 outcome에서 충돌하지 않는지 연결한다. 이후 재귀 규모를 늘린다.

HSWM-likeness에서는 실행 연결의 부분 근거를 추가한다. 형식·실행·효능을 별도로 유지하며
전체 판정은 계속 `GAPS_REMAIN`이다. 전체 HSWM이나 metahumotonic 완성의 증명은 아니다.
