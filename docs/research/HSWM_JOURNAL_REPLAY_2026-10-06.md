# HSWM journal 복구의 바이트와 상태 대응

2026-10-06 · `SECONDARY_AI_ENGINEERING_VALIDATION`

[작업 계획](HSWM_STANDARD_GRAPH_PROGRESS_PLAN_2026-10-06.md)의 T1에서, 실제 journal 복구가
사용하는 predecessor·schema·receipt 검사를 순수 함수로 추출하고 Lean 4에 연결했다.
정확한 재인코딩을 요구하는 decoder 모델과, 유한한 decoded 기록열의 상태·이력 보존을
증명했다. 실제 파일 저장소에서 생성한 두 전이의 복구 결과와 변조 거절을 대조했다.
**T1은 제한 범위의 연결이 검증된 상태다. JSON 파서·native evolution 전체의 정제 증명은 남아 있다.**

## 실제 복구 경로와 연결한 범위

[journal 구현](../../src/hswm/effect-runtime/src/canonical-atom-v2-state-journal.ts)은 기존 검사 순서와
오류를 유지하며 [순수 guard](../../src/hswm/effect-runtime/src/canonical-atom-v2-journal-replay-guards.ts)를
호출한다. decoder·envelope·receipt의 바이트 비교는 이전에 증명한 exact-byte 함수를 재사용한다.
새 권한, 쓰기 경로, journal 형식이나 RDF profile을 도입하지 않는다.

| 연결 | 형식 모델의 보장 | 실제 구현에서 확인한 것 |
| --- | --- | --- |
| 바이트→decoded record | decoder가 값을 수락하면 그 값의 재인코딩은 입력 바이트와 정확히 같다. 같은 값을 수락한 두 표현의 바이트도 같다. | 실제 duplicate-free parser와 strict schema decoder를 통과한 바이트를 재인코딩. 중복 필드·escape로 숨긴 중복·잘린 JSON·초과 필드·잘못된 숫자·UTF-8·초과 크기 거절. 공백과 대체 escape 표기는 `RECORD_NOT_CANONICAL`. |
| predecessor·schema→receipt | lineage, 전체 descriptor와 다음 revision, schema binding, receipt의 이전/다음 revision과 범위 표기가 일치해야 한다. | 실제 저장된 record를 재직렬화해 lineage·descriptor·schema·revision·digest를 바꾼 사례의 오류와 Lean 판정을 대조. |
| receipt·envelope→후속 상태 | receipt의 schema·이전 revision·transition ID와 decoded writes로 command를 구성한다. 보존 조건을 통과한 상태만 모델에서 반환한다. | stored envelope를 읽고 실제 `applyCanonicalAtomV2StateJournalCommit`로 상태와 expected receipt를 계산한다. write-set 바꿔치기는 전체 receipt 재구성 비교에서 거절된다. |
| 유한 복구열 | 성공한 전체 기록열은 원본 atom·schema·이력 prefix와 lineage를 유지하며 revision이 기록 수만큼 증가한다. 실패한 prefix 뒤에 기록을 붙여도 전체 복구는 실패한다. | 같은 저장소의 bootstrap과 scripted semantic revision 두 건을 genesis부터 재생. 누락·순서 뒤집기·중복 적용을 거절하고 fresh Layer로 다시 연 상태·history·raw journal과 비교. |

`decodeExact`의 parser와 encoder는 매개변수다. 실제 TypeScript JSON 파서가 모든 입력에서
Lean의 JSON 의미를 구현한다는 증명이 아니다. exact-byte 조건의 증명과 파서 동작의
실행 검사를 구별한다. SHA-256 충돌 저항성이나 서로 다른 값의 digest 일치가 원본 동일성을
뜻한다는 공리를 추가하지 않았다.

Lean의 `Witness`에는 실제 adapter가 계산한 후속 native image, decoded writes, 상태 digest,
receipt 바이트와 새 descriptor를 전달한다. `accepted`는 **필요한 복구 조건의 모델**이며
독립적인 완전한 journal validator가 아니다. envelope decode·content binding·schema validation·
native evolution의 성공과 그 출력의 대응을 전제로 한다. 실제 runtime의 권한 검사나
실행기를 이 모델로 교체하지 않는다.

## 검증 결과

[Lean 모듈](../../formal/HSWMJournalReplay.lean)은 보조정리를 포함해 정리 25개를 갖는다.
`decode_exact_binds_bytes`, `accepted_receipt_revision`, `finite_replay_extends`,
`finite_replay_revision`, `failed_prefix_rejects_extension`이 핵심 연결이다.
[비교 CLI](../../formal/HSWMJournalReplayCli.lean)는 실제 관측을 입력받고 모든 결과에
`jsonParserProved: false`, `nativeEvolutionProved: false`, `permissionProved: false`를 반환한다.

[새 테스트](../../tests/effect-runtime/journal-replay.test.ts)는 같은 실제 graph-loop 경로에서
bootstrap과 scripted semantic revision을 생성한다. 모델 응답은 fixture이며 실제 LLM
호출은 없다. Lean 대조 50건은 단일 전이 2, 기록열 5, codec 관측 22, record 변경 14,
receipt/native image 변경 4, header 범위 거절 2, 비인증 actor 변경 1로 구성된다.
CLI의 byte 256과 음수 revision 거절도 확인했다.

세 추가 파일 변조 검사는 테스트 소유의 임시 저장소에 한정한다. tail record의 receipt,
resulting-state digest 또는 직렬화를 바꾸고 object 파일 이름을 새 해시로 바꾸어 raw
hard-link 복구는 통과시킨다. 새 runtime은 각각 `RECEIPT_INVALID`, `STATE_DIGEST_INVALID`,
`RECORD_NOT_CANONICAL`로 거절한다. 새 OS 프로세스의 crash/power-loss qualification과는
다른 검사다.

관련 8개 파일의 회귀 검사 57건이 통과했고, 이후 파일 변조 검사 3건을 추가한 새 파일의
6개 테스트도 통과했다. 중복 실행을 제외하면 총 60개 테스트다. TypeScript·temporal·Effect·
functional 검사, runtime build, Lean library·CLI build도 통과했다.

Lean 4.32.1의 `journal-replay` audit profile은 의존 소스 3개를 별도 경로에 `--trust=0`으로
다시 컴파일했다. 새 25개 정리의 공리 의존성은 `propext`, `Quot.sound`이고 상태는
`EXACT_SOURCE_KERNEL_CHECKED`다. 새 사용자 공리나 `sorry`·`admit`·`native_decide`는 없다.
이전 두 의존 모듈의 모든 정리를 이번 profile에서 개별 재감사한 것은 아니다.

## 권한에 관해 남는 중요한 구별

receipt의 `actorClaim`만 구조적으로 유효하게 변경하면, 복구는 그 입력에서 일관된 receipt를
재구성하고 같은 native 상태를 반환할 수 있다. 이 수락 사례를 TypeScript와 Lean에서
함께 확인했다. **복구 성공은 actor 인증이나 서명 검증이 아니다.** 참조 grant와 canonical
Permit의 차이를 숨기지 않으며 기존 권한·부정 결과·HSWM_LIKENESS 판정은 유지한다.

다음 T1 작업은 schema/envelope decoding, receipt 재구성과 native evolution의 실제 adapter
대응을 더 좁혀 검증하는 것이다. T2는 기존 signed Permit의 신뢰된 key·scope·nonce·clock·head
조건을 같은 실행 기록에 연결한다. T3의 실제 게시·OS 장애 모델과 LLM 의미 실행 W1은
기존 계획대로 별도 의무다. 이번 증명으로 PS-3 전체, T1 전체 또는 학습 효능을 완료 처리하지 않는다.

## 표준 그래프와 재현

[진행 연결](../../ontology/development/HSWM_JOURNAL_REPLAY_PROGRESS_2026-10-06.v1.json)은 기존
T1 UID와 계획을 참조하고 `PARTIAL_BOUNDARY_PROVED_REFINEMENT_OPEN`을 기록한다.
Claim→Decision, Claim/Decision→Source, Decision→Claim 범위 관계를 기존 어휘로 표현한다.
새 판정은 `SECONDARY_AI`; 과거 계획의 bytes와 상태는 보존한다. 각 Claim의 현재 Decision은
정확히 하나이고, Decision은 해당 Claim 하나만 `CONSTRAINS`하며 근거는 하나 이상이다.
Source는 정확한 파일 바이트에 결속되고 anchor는 참조만 한다.

기존 bundle v2로 RDF·PROV view를 만들고 SHACL 및
[현재 T1의 판정·근거 질의](../../ontology/queries/hswm_progress_plan_2026-10-06/journal-replay.rq)를
검사한다. 결과는 [검증 기록](artifacts/hswm_journal_replay_2026-10-06/validation.v1.json)에 있다.
표준 그래프 통과는 모델의 현실 전제나 권한을 증명하지 않는다. 원격 KG에 게시하지 않는다.

```sh
# cwd: formal
lake build HSWMJournalReplay HSWMJournalReplayCli

# cwd: HSWM root
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime run build
HSWM_RUN_SEMANTIC_LEAN=1 npm --prefix src/hswm/effect-runtime test -- ../../../tests/effect-runtime/journal-replay.test.ts --maxWorkers=1
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile journal-replay --output NEW_PRIVATE_DIRECTORY
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source replay=ontology/development/HSWM_JOURNAL_REPLAY_PROGRESS_2026-10-06.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source replay=ontology/development/HSWM_JOURNAL_REPLAY_PROGRESS_2026-10-06.v1.json --profile v2 --query ontology/queries/hswm_progress_plan_2026-10-06/journal-replay.rq
```

호스트별 Lean 감사 원문은 `.local/journal-replay-2026-10-06/lean-audit-final/`에 보존한다.
