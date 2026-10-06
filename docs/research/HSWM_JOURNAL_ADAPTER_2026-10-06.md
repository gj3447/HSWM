# HSWM journal의 envelope·receipt·후속 상태 구성 대응

2026-10-06 · `SECONDARY_AI_ENGINEERING_VALIDATION`

[기존 작업 계획](HSWM_STANDARD_GRAPH_PROGRESS_PLAN_2026-10-06.md)의 T1을 이어서,
[이전 replay 증명](HSWM_JOURNAL_REPLAY_2026-10-06.md)이 외부 witness로 받던
receipt 재구성과 후속 상태 구성을 실행 가능한 Lean 함수로 옮겼다. 실제 파일 저장소의
bootstrap·scripted semantic revision에서 같은 입력을 추출하여 TypeScript 결과와 대조한다.
**상태를 구성하는 모델의 보존은 증명하지만, 모든 native validator와 JSON adapter의
TypeScript 소스 정제 증명이 완료된 것은 아니다.** T1 전체는 계속 미완료다.

## 연결한 계산

| 계산 | 실제 production 경로 | Lean의 범위 |
| --- | --- | --- |
| envelope binding | strict JSON/schema decode와 정확한 재인코딩 이후, 계산된 envelope descriptor·key ID·payload를 binding과 비교한다. | 관측된 descriptor의 전체 일치, 고정 media type, key ID와 payload의 일치. 파서·SHA-256 계산은 외부 경계다. |
| receipt→command | receipt의 transition·이전 revision·schema·metadata·read-set을 복사하고 실제 decoded envelope를 writes로 넣는다. | 동일한 필드 복원. receipt가 주장한 write-set을 writes의 원본으로 사용하지 않는다. |
| command→candidate | 기존 atom과 writes를 정렬하고 revision을 한 번 증가시키며 bootstrap을 닫고 transition 이력을 하나 덧붙인다. | 후속 상태를 직접 계산한다. 정렬 전후 permutation으로 atom의 보존과 추가되지 않은 atom의 부재를 증명한다. |
| command→receipt | read-set과 실제 write keys를 정렬하고 고정 guard·decision 및 입력 metadata를 넣는다. | 전체 receipt를 직접 재구성한다. 일치한 receipt의 write-set은 실제 writes에서 계산된 키 목록이다. |

[순수 adapter](../../src/hswm/effect-runtime/src/canonical-atom-v2-journal-adapter.ts)는
기존 [journal 경로](../../src/hswm/effect-runtime/src/canonical-atom-v2-state-journal.ts)에서 사용된다.
[domain](../../src/hswm/effect-runtime/src/canonical-atom-v2-domain.ts)의 후보 상태 구성과 키 비교도
기존 구현 그대로 추출해 실제 `evolveValidatedCanonicalAtomsV2`가 호출한다. schema·state·command·
provenance 검증 및 최종 preservation 검사의 순서는 유지한다. constructor는 admission API가 아니다.

`native_candidate_preserves`의 전제는 입력에만 걸린다. writes가 비어 있지 않고, 기존 키와
쓰기 키가 각각 유일하며 서로 겹치지 않고, transition ID가 새 것이며, revision 증가가
JavaScript 안전 정수 범위에 있고 command의 schema·이전 revision이 일치해야 한다.
결론은 계산된 후보 상태가 기존 `CanonicalPreservation.preserves`를 만족한다는 것이다.
후속 상태가 보존된다고 미리 가정하는 증명이 아니다. 이후 `ExtendsNative`와 연결한다.

정렬에는 두 계약이 있다. state·receipt는 schema/lineage/atom 문자열 뒤에 revision을
**숫자**로 비교한다. journal의 write binding은 `canonicalAtomV2KeyId` **문자열** 오름차순이다.
revision 2와 10에서 순서가 다를 수 있다. 이를 통일하거나 기존 wire 계약을 바꾸지 않는다.
키 문자열의 구분자 `|`는 native identifier 문법에 포함되지 않는다. Lean의 key-ID 모델이
임의 문자열 전부에 대해 구조적 키의 단사성을 증명한다는 주장은 하지 않는다.
정렬 대응 검사는 native ASCII identifier와 안전 정수에 한정한다. CLI는 임의 Unicode,
구분자가 포함된 문자열, SHA 형식이나 초과 JSON 필드를 native schema처럼 검증하지 않는다.

## 실행 검사의 의미

[비교 테스트](../../tests/effect-runtime/journal-adapter.test.ts)는 실제 파일 저장소의 두 전이를
복구하고 production envelope·receipt·native state를 추출한다. Lean CLI에는 이전 상태,
receipt와 writes만 주며, 기대하는 후속 상태나 재구성된 receipt를 입력하지 않는다.
전체 계산 결과를 TypeScript와 비교한다. 의미 모델 응답은 fixture이며 실제 LLM 호출은 없다.

다음 반례를 함께 유지한다.

- receipt의 write-set·next revision·read-set 순서를 바꾸면 재구성 결과와 달라진다.
- 중복 read-set은 후보 상태 보존 검사만으로 발견되지 않는다. 실제 native evolution은
  `READ_SET_INVALID`로 거절한다. 이는 보존과 구조적 유효성이 다른 의무임을 보여 준다.
- actor·authorizationRef·scope·시간·provenance digest를 일관되게 바꾸어도 journal replay는
  같은 상태를 반환할 수 있다. metadata 복사는 인증이나 canonical Permit 검증이 아니다.
- envelope의 media type·길이·digest·키·payload 변경, 중복 JSON 필드·비정규 공백·잘린 입력,
  envelope 개수/위치 불일치를 실제 journal 경로가 거절한다.
- 2/10 revision 정렬과 constructor의 snapshot 분리를 검사한다. 합성 입력에 대한 후보
  구성 성공은 native bootstrap/provenance validation의 성공으로 간주하지 않는다.

[Lean CLI](../../formal/HSWMJournalAdapterCli.lean)의 모든 결과에는 `jsonParserProved: false`,
`nativeValidationProved: false`, `permissionProved: false`를 포함한다. complete envelope image는
기존 preservation adapter가 만든 정규화된 문자열이다. 이 문자열이 임의의 native JSON과
정확히 대응한다는 보편 정리, Node 해시/암호 구현 및 OS 영속성은 이번 모델 밖이다.
Lean의 receipt 일치는 decoded 전체 필드의 구조적 동등성이다. native journal은 snapshot의
canonical JSON 바이트를 비교한다. 두 결과의 실제 실행 대조를 제공하지만, 임의 입력의
encoder 단사성이나 receipt 바이트 동등성 자체를 이번 Lean 모듈에서 증명하지 않는다.
고정 tag/version은 이미 native decoder에서 확인된 입력을 전제로 하며 CLI 출력에 상수로 넣는다.

새 모듈은 이름 붙은 정리 31개다. Lean 4.32.1로 의존 소스 3개를 별도 경로에서
`--trust=0`으로 컴파일하고, 새 정리 31개의 공리 의존성을 검사한 결과
`EXACT_SOURCE_KERNEL_CHECKED`다. 관측된 공리는 `Classical.choice`, `Quot.sound`, `propext`이며
새 사용자 공리나 증명 생략은 없다. 의존 모듈의 모든 정리를 이번에 개별 재감사한 것은 아니다.

새 파일 6개 테스트와 기존 관련 10개 파일 108개 테스트, 총 114개가 통과했다.
새 Lean 대조는 1,397건이다: 실제 전이 2, receipt·state·writes 변경 12, envelope binding 11,
합성 정렬 3, ASCII/숫자 comparator 1,369. CLI의 음수·소수·안전 범위 초과 revision 거절도
검사했다. 첫 대조에서 CLI의 receipt tag/version 출력 누락을 찾아 수정하고 새 파일을 다시
실행했다. TypeScript·temporal·Effect/functional 검사, runtime 및 Lean build도 통과했다.
호스트별 원본 로그와 fresh audit는 `.local/journal-adapter-2026-10-06/`에 남긴다.

## 표준 그래프 진행 기록

[새 진행 bundle](../../ontology/development/HSWM_JOURNAL_ADAPTER_PROGRESS_2026-10-06.v1.json)은
기존 T1·계획·이전 replay 기록을 참조한다. 기존 스냅샷을 덮어쓰지 않고 scoped Claim,
현재 Decision 하나와 정확한 source bytes를 연결한다. 기존 RDF 1.1·PROV·SHACL·SPARQL
도구를 사용한다. 검증 결과와 범위는
[검증 기록](artifacts/hswm_journal_adapter_2026-10-06/validation.v1.json)에 보존한다.
RDF view의 write-back은 `FORBIDDEN`이고 원격 KG 게시는 하지 않는다.

T1 상태는 `PARTIAL_PRODUCER_PROVED_REFINEMENT_OPEN`이다. 전체 HSWM 증명, 실제 학습 효능,
HSWM_LIKENESS의 새 측정값으로 승격하지 않는다. 과거 PS-1~PS-6와 부정 실험 결과는 유지한다.

## 다음 연결

T1에는 strict schema/envelope decoding과 전체 native validation의 adapter 의무가 남는다.
T2의 caller-relative signed Permit 경로는 이미 구현돼 있다. 기존
[envelope 테스트](../../src/hswm/effect-runtime/test/canonical-atom-v2-permit-envelope.test.ts)는
key·scope·nonce·시간·head 변조를, [V2 gateway 테스트](../../src/hswm/effect-runtime/test/canonical-atom-v2-verified-admission-gateway-v2.test.ts)는
두 전이와 재시작, 정확한 Lean wire 저장 및 변조 거절을 다룬다. 이번에는 소스를 읽어
확인했으며 이 T2 테스트를 새로 실행했다고 주장하지 않는다. V2 검사는 Lean binary가
없으면 건너뛰므로 실행 증거를 낼 때 실제 binary 존재와 호출을 확인해야 한다.

남은 T2 연결은 [gateway](../../src/hswm/effect-runtime/src/canonical-atom-v2-verified-admission-gateway.ts)가
native 검증 뒤 전달하는 `permitEnvelopeAccepted`, `stateBytesAccepted`,
`verificationTimeAccepted` 세 사실이다. [Lean CLI](../../formal/HSWMAdmissionKernelCli.lean)는
이를 caller가 공급한 전제로 받는다. 저장된 wire의 digest·head·nonce만으로는 key 신뢰·scope
권한·검증 성공을 도출하지 못한다. 다음 작업은 **native preflight 성공에서 세 adapterFacts로
가는 대응**을 증거와 함께 구성하는 것이다. 이미 있는 변조 테스트를 되풀이하거나 새
추상 Permit checker를 만드는 것으로 이 공백을 닫지 않는다.

T3는 실제 게시·OS 장애 모델의 의무를 맡는다. 서로 다른 경로의 성공 기록을 자동으로
하나의 끝에서 끝까지 증명으로 합치지 않는다.

```sh
# cwd: formal
lake build HSWMJournalAdapter HSWMJournalAdapterCli

# cwd: HSWM root
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime run build
HSWM_RUN_SEMANTIC_LEAN=1 npm --prefix src/hswm/effect-runtime test -- ../../../tests/effect-runtime/journal-adapter.test.ts --maxWorkers=1
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile journal-adapter --output NEW_PRIVATE_DIRECTORY
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source adapter=ontology/development/HSWM_JOURNAL_ADAPTER_PROGRESS_2026-10-06.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source adapter=ontology/development/HSWM_JOURNAL_ADAPTER_PROGRESS_2026-10-06.v1.json --profile v2 --query ontology/queries/hswm_progress_plan_2026-10-06/journal-adapter.rq
```
