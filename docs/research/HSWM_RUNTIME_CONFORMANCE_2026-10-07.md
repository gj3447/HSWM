# HSWM runtime conformance: decoder, signed Permit, V2 recovery

2026-10-07 · `SECONDARY_AI_ENGINEERING_VALIDATION`

[앞선 preflight 증명](HSWM_NATIVE_PREFLIGHT_REFINEMENT_2026-10-07.md)의 T1–T4를
이어 실제 decoder, 상세 Permit 모델, V2 프로세스 장애와 같은 전이의 읽기까지 연결한다.
이번 근거는 decoded-model 정리와 실제 구현의 유한 대조다. 전체 구현의 보편적 정제나
실제 LLM 효능을 증명했다는 뜻은 아니다. JSON parser·hash·암호·caller trust/time의
외부 전제와 두 장부의 권한 차이를 남긴다.

## T1: 실제 envelope decoder와 record producer

[production helper](../../src/hswm/effect-runtime/src/canonical-atom-v2-journal-decode-guards.ts)를
기존 state journal의 실제 경로에서 사용한다. bounded duplicate-free JSON → 엄격한 atom
schema → exact canonical encoding → 관측 envelope descriptor·key·payload descriptor
일치를 검사한다. object 입력과 byte 입력의 기존 오류 코드·메시지를 보존한다.

[Lean 모델](../../formal/HSWMJournalDecode.lean)은 `JournalAdapter.Atom`과 기존
`EnvelopeBinding`을 사용한다. raw/canonical bytes를 실제로 비교하고, 관측 media type과
전체 descriptor, atom key와 payload descriptor를 비교한다. 외부에서 넣은 전체 승인
boolean으로 이 비교를 대신하지 않는다. 각 write의 image를 기존 replay witness의 writes와
결속하고 exact receipt·revision·native preservation 정리에 연결한다.

`produced_replay_accepted`는 Fresh command와 schema 일치에서 constructor가 만든
record·witness의 replay 승인을 도출한다. `produced_decoded_commit_accepted`는 이를
검사된 envelope images와 합성한다. 성공한 replay를 전제하고 같은 성공을 결론으로
내놓는 정리만 있는 것은 아니다. 관측 digest와 receipt encoding의 producer 자체는
여전히 외부 경계다.

[실행 대조](../../tests/effect-runtime/journal-decode.test.ts)는 잘린 JSON, 중복 key,
비정규 spelling, descriptor/key/payload 바꿔치기와 개수 불일치를 native decoder로 거절한다.
새 CLI는 `DecodedWrite` 전체 필드를 해석해 실제 `writeMatches`를 호출한다.
정상 1개와 변형 11개의 모델 결과를 native helper와 대조한다. 기존 adapter/replay
검사에서 실제 journal record의 잘못된 revision·schema·receipt·state digest 처리도 유지한다.
CLI의 JSON 해석 코드 자체를 Lean에서 검증한 것은 아니다.

## T2: 상세 signed-Permit 모델에서 preflight로

[순수 projection](../../src/hswm/effect-runtime/src/canonical-atom-v2-verified-permit-bridge.ts)은
native verifier의 성공 결과를 그대로 관측한다. production preflight가 이 helper를 사용한다.
투영은 서명된 bytes의 hash와 검증 시각, intent·nonce·heads, caller의 trust/key provenance를
보존하며 새로운 인증기로 사용하지 않는다. 구조적으로 만든 투영은 권한 증명이 아니다.

[bridge 정리](../../formal/HSWMVerifiedPermitBridge.lean)는 native projection과 decoded
Permit claims의 명시적 대응 전제 아래, 기존 `canonicalPermitEnvelopeAccepted` 정리에서
expected context 일치와 같은 lineage의 즉시 후속 head 조건을 도출한다. 남은 journal
전제는 nonce freshness와 recovered head/genesis의 일치이며, bounded state-byte 조건과
합성해 기존 admission kernel 승인으로 연결한다. native envelope-byte hash와 clock을
추상 signed-document 모델이 계산한다는 주장은 하지 않는다.

[새 CLI](../../formal/HSWMVerifiedPermitBridgeCli.lean)는 envelope header·claims·expected
bindings 전체를 해석하고 기존 Permit checker를 직접 실행한다. `externalObservations`는
canonical bytes, trust snapshot, key policy/epoch, authorizer, key 활성 시간, Permit 활성 시간,
서명 검사 결과를 각각 표시한다. 이 외부 관측의 참이라는 입력 자체를 증명으로 세지 않는다.

[대조 검사](../../tests/effect-runtime/verified-permit-bridge.test.ts)는 공개 서명 vector를
실제 native verifier에 넣는다. 정상 vector와 13가지 expected-binding 변형의 native/Lean
결과가 일치한다. 일곱 외부 관측 중 하나가 거짓일 때 모델이 거절하는 검사도 따로 수행한다.
후자는 암호나 시간 계산의 독립 검증이 아니다. 실제 signature/trust/time 거절은 기존 native
Permit 검사와 함께 회귀 검증한다.

## T3–T4: V2 전용 장애와 동일 전이의 두 장부

기존 별도 process 검사는 일반 state journal의 race와 **V1** Permit store의 crash를
다뤘다. 이를 V2 전용 crash 검증으로 세지 않는다. 이번에는 기존 public factory의 기본
동작을 유지하고 test-only checkpoint factory에서 **실제 V2 gateway와 Lean hook**을 실행한다.
새 child process는 준비 파일 fsync 뒤 또는 slot hard-link 뒤에 SIGKILL로 종료된다.
재시작은 각각 이전 prefix 또는 정확한 successor를 복구해야 한다. V2 경쟁도 같은 namespace의
no-replace 게시를 통과시킨다. 실행 범위는 이 검사 호스트의 Linux/tmpfs이며 디스크 전원 손실,
장부 전체 rollback, 전역 nonce 보전이나 분산 합의는 검증하지 않는다.

V2 persisted status literal의 `PROCESS_CRASH_NOT_TESTED`는 기존 byte/schema 계약 때문에
그대로 유지한다. 현재 시험 여부는 이 source-bound 검증 기록으로 읽으며, 과거 저장 bytes의
문구를 소급해서 바꾸지 않는다.

[동일 전이 검사](../../tests/effect-runtime/journal-v2-durability-trace.test.ts)는 실제 native
후보의 pre/post state bytes와 journal descriptor를 계산하고, 그 bytes를 Permit과 Lean
승인에 결속한 뒤 domain journal 기록과 재시작 후 content read frame에 대조한다.
Permit protected journal과 reference-grant domain journal은 별도의 장부다. 관측값과
순서가 일치해도 두 게시를 하나의 원자적 권한 트랜잭션으로 만드는 정리는 아니다.

## 최초 계획의 완료 범위

T1은 decoded model에서 decode→receipt→state와 유한 replay 보존, 실제 구현의 유한
거절 대조, JSON decoder 경계의 분리라는 기존 완료 조건을 충족한다. T2도 같은
유효·거절 trace의 native/Lean 결과 일치와 외부 key·time·nonce 전제 명시라는 조건을
충족한다. 전체 TypeScript·암호 구현의 보편적 증명은 이 두 작업의 완료 조건에 넣지 않았다.
T3의 완료 범위는 명시한 Linux/tmpfs의 V2 process crash와 race다.

T4는 한 실행에서 관측한 정확한 바이트와 Lean 교환을
[보존된 실행 trace](artifacts/hswm_runtime_conformance_2026-10-07/same-run-trace.v1.json)에
남긴다. trace는 합성 fixture에서 실제 실행한 결과이며, private key는 포함하지 않는다.
Git source revision·source hashes, signed envelope, domain journal, pre/post state,
복구된 snapshot·content, 실제 Lean request/response bytes를 결속한다. 표준 진행 view의
`trace` 질의는 이 실행의 바이트 근거와 결과·출처를 조회한다. 두 장부의 원자적 권한
통합은 별도 경계이며 이 trace의 완료 조건을 소급해서 확대하지 않는다.

T1–T4 완료는 2026-10-06 계획의 위 기준에 대한 판정이다. 전체 HSWM 증명이나
PS-3·5·6 및 CR/FCL 효능 판정의 완료를 의미하지 않는다.

## 검증과 남은 실제 모델 작업

새 모델의 named theorem은 T1 13개, T2 6개다. Lean 4.32.1의 fresh 출력 디렉터리,
`--trust=0`, 정확한 source hashes와 전체 named theorem의 axiom 의존성 감사로 확인한다.
허용 공리는 기존 `Classical.choice`, `Quot.sound`, `propext` 집합이다. 의존 모듈을
컴파일하되 그 모든 정리를 이번에 새로 개별 감사했다고 세지 않는다.

정확한 실행 결과·개수·소스 결속은
[검증 기록](artifacts/hswm_runtime_conformance_2026-10-07/validation.v1.json)에 둔다.
원본 로그와 호스트별 세부사항은 `.local/refinement-closure-2026-10-07/`에 보존한다.

T5의 기존 원본 W1 입력 128사례·384요청을 다시 준비했다. 현재 checkout의 문서상
project-local USL mapping 디렉터리와 실행 wrapper는 확인되지 않았고, 현재 모델·tokenizer·
template·checkpoint·serving attestation도 확립하지 못했다. 이는 제한된 경로 점검이며
다른 원격 서버가 없다는 결론은 아니다. 실제 모델 생성 요청은 0개다. 원본 384요청 준비와
전체 2,784요청 W1 실행·통과를 구별한다.

T6의 학습 대조, T7 읽기 선택 효용, T8 공동 효과, T9 상위 합성은 그 실측 전제를 기다린다.
PS-3·5·6, 기존 음성 결과와 CR/FCL 완료 판정은 승격하지 않는다. 후속 표준 그래프는
현재 관측과 이전 관측을 별개로 보존하며, 이 연구 view는 canonical AI 학습 상태가 아니다.
