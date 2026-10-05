# Graph loop 사전 검사와 Lean 대응

2026-10-05 · `SECONDARY_AI_ENGINEERING_VALIDATION`

[초기화 연결 이후의 첫 후속 작업](HSWM_SEMANTIC_BOOTSTRAP_ADMISSION_2026-10-05.md)을 진행했다.
실제 controller의 snapshot freshness와 candidate read-set 검사를 순수 함수로 추출하고,
대응하는 decoded Lean 모델에 정리 14개를 추가했다. 국소 입력이 같아도 전역 revision이
바뀌면 이전 후보가 거절되는 사례를 실제 파일 저장소에서 확인했다. 전체 admission이나
학습 효능을 증명한 결과는 아니다.

## 구현과 증명

[순수 TypeScript 검사](../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-guards.ts)는
head의 lineage, revision, state digest, journal descriptor, schema binding을 비교한다.
candidate에는 schema와 revision 일치, trace 부재, 하나 이상의 write,
affected key의 read-set 포함, read key의 canonical 상태 포함을 요구한다.
빈 match는 revision 0이며 canonical key와 read-set이 모두 빈 genesis에만 허용한다.
파일 읽기와 실제 승인은 기존 Effect controller에 남긴다.

[Lean 모델](../../formal/HSWMGraphLoopPreflight.lean)은 같은 decoded 필드에 관한
검사 동치, 오래된 head 거절, read-set 포함 관계, write 존재, genesis 조건을 증명한다.
국소 payload와 사전 검사 결과를 함께 보존하는 충분조건은 head와 canonical key 목록이
같고, 선택된 역할의 본문이 같은 것이다. key 목록 전체의 동일성은 보수적인 조건이며
최소 필요조건이라는 주장은 하지 않는다. 국소 read만 같아서는 사전 검사 결과가 보존되지
않는 구체적인 반례도 포함했다.

해시 계산, JSON decoding, key encoding, JavaScript 숫자 의미론, 권한, evidence의 진실성,
전체 schema 검사, 원자적 CAS와 crash recovery는 이 모델의 증명 범위 밖이다.
[비교용 CLI](../../formal/HSWMGraphLoopPreflightCli.lean)는 항상 `admissionProved: false`를
반환하며 승인 endpoint가 아니다. TypeScript와 Lean의 사례별 일치는 모든 실행의 refinement
증명을 대신하지 않는다.

## 실제 저장소에서 확인한 경계

[통합 테스트](../../tests/effect-runtime/graph-loop-preflight.test.ts)는 같은 snapshot에서
두 run을 준비한 다음, 한 run으로 국소 read와 무관한 atom을 추가한다. 전후의 event,
relation, 순서가 있는 roles, priorEvidence는 같지만 revision과 frame digest는 달라진다.
먼저 준비한 후보를 제출하면 `QUARANTINED`가 되고, 그 거절로 canonical 상태는 바뀌지 않는다.
이는 순서대로 재현한 충돌 사례이며 모든 동시 실행의 보장은 아니다.

현재 [LLM 요청 생성](../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.ts)은
`executionId`와 `stateRevision`, `frameSha256`를 포함한 전체 frame을 prompt에 직렬화한다.
따라서 여기서 보존한 국소 payload와 모델이 보는 전체 요청 바이트는 구별해야 한다.
모델 요청의 국소성까지 요구하려면 버전이 명시된 prompt projection과 provenance 기록의
관계를 별도로 정의하고 검증해야 한다. 이번에는 기존 v1 요청 계약을 변경하지 않았다.

## 검증 결과

- Lean 4.32.1에서 관련 library와 새 CLI build 통과.
- 새 profile `graph-loop-preflight`로 import closure 3개를 `--trust=0`으로 새로 컴파일했다.
  새 정리 14개의 공리 의존성은 `propext`, `Quot.sound` 범위이며 상태는
  `EXACT_SOURCE_KERNEL_CHECKED`다. 의존 파일 전체의 정리를 개별 감사했다는 뜻은 아니다.
- TypeScript, temporal, Effect boundary, functional 검사와 runtime build 통과.
- 관련 7개 파일의 테스트 22개 통과. 실제 head 및 각 검사 필드의 변조를 포함한
  decoded 사례 24개를 Lean CLI와 대조했고, 잘못된 음수 입력의 거절도 확인했다.
- 기존 local semantic instrument의 HTTP fixture 테스트 3개 통과. 실제 모델 호출은 아니다.
- 전체 suite는 재실행하지 않았다. 기존 Node pin 관련 실패 기록과 과거 학습 음성 결과를 유지한다.

재현 명령은 HSWM root 기준이며, Lake 명령만 `formal`에서 실행한다. 감사 출력 경로는
새 디렉터리여야 한다.

```bash
# cwd: formal
lake build HSWMSemanticLifecycleRefinement HSWMGraphLoopPreflightCli

# cwd: HSWM root
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime run build
HSWM_RUN_SEMANTIC_LEAN=1 npm --prefix src/hswm/effect-runtime run test -- ../../../tests/effect-runtime/graph-loop-preflight.test.ts test/canonical-atom-v2-graph-loop-engineering.test.ts test/canonical-atom-v2-graph-loop-enforcement-boundary.test.ts ../../../tests/effect-runtime/semantic-lifecycle-bootstrap.test.ts ../../../tests/effect-runtime/semantic-lifecycle-chain.test.ts ../../../tests/effect-runtime/semantic-lifecycle-refinement.test.ts ../../../tests/effect-runtime/semantic-philosophy-proof-process.test.ts --maxWorkers=1
node --test tests/research/local-semantic-execution-instrument.test.mts
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile graph-loop-preflight --output NEW_PRIVATE_DIRECTORY
```

## 실험 준비와 남은 작업

[HSPINE 연구안](https://metahumotonic.com/hspine?thread=thread-1179014f-6ec6-4c26-a522-07a78ea7ca72)은
oracle 수행 가능성, 실제 의미 변경, 독립적인 학습 이득, 두 셀의 공동 학습 순으로 검증을
제안한다. 이는 `AI_PROPOSAL`이며 완료된 실험이나 canon으로 취급하지 않는다.

기존 [local semantic instrument](../../_research/local_semantic_execution_v1/README.md)로
입력 128개와 정확한 요청 384개를 준비하고 source 및 request pin을 검사했다.
상태는 `PREPARED_NOT_RUN`, 실제 모델 요청은 0회다. 이 instrument 내부의 E0/E1/E2는
세 출력 형식을 뜻하며, HSPINE 연구안의 세 실험 단계와 같지 않다. 준비된 384개 요청은
전체 W1 변환·sentinel 실험이나 학습 효과 평가를 완료한 것이 아니다.

다음 실행에는 실제 serving checkpoint, tokenizer와 runtime의 확인 및 사용 가능한 실행 경로가
필요하다. 그 뒤 oracle의 수행 가능성을 먼저 확인하고, frozen/evidence-only/sham/learned와
제거·복원 조건을 독립 평가한다. 실제 효과가 확인된 후 두 셀과 더 큰 구조를 검토한다.
HSWM-likeness의 이전 평가를 재채점하지 않았으며 전체 증명 상태는 계속 `GAPS_REMAIN`이다.
