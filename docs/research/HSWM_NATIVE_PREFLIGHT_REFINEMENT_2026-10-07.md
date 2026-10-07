# HSWM native preflight·읽기 집합 검증의 Lean 대응

2026-10-07 · `SECONDARY_AI_ENGINEERING_VALIDATION`

[통합 진행 그래프](HSWM_PROGRESS_CONSOLIDATION_2026-10-07.md)의 T2와 T1을 함께 진행했다.
T2는 실제 native 검사 결과에서 Lean admission의 세 입력 사실을 계산하도록 연결했고,
T1은 기존 상태 키와 읽기 집합의 중복·해소 검사를 production 함수에서 추출했다.
두 경계의 Lean 모델과 실제 TypeScript 실행을 대조하고 새 소스를 별도 커널 감사했다.
전체 TypeScript 정제, JSON parser, 암호, 신뢰 체계, 시간, OS 영속성은 별도의 남은 의무다.

## T2: 검사된 값에서 admission 사실을 계산

기존 gateway의 `adapterFacts`는 상수 `true` 세 개였다. 그 이전 native 경로에서는
실제로 Permit·서명·caller-relative trust·시간·상태 바이트를 검사하고 있었지만, 그 검사와
Lean에 전달하는 값의 대응이 별도 계산으로 드러나지 않았다.

[새 순수 adapter](../../src/hswm/effect-runtime/src/canonical-atom-v2-admission-preflight.ts)는
다음 값을 받는다. `verifiedPermit`은 실제 verifier가 성공한 뒤 만든 투영이고,
`preState`·`postState`는 검사된 실제 바이트의 길이와 SHA-256 관측이다.

| Lean 입력 사실 | 계산하는 일치 조건 |
| --- | --- |
| `permitEnvelopeAccepted` | record의 envelope digest·intent·nonce·이전/다음 head 전체가 성공한 verifier 투영과 일치 |
| `verificationTimeAccepted` | committedAt·verificationTime 둘 다 verifier가 검사한 checkedAt과 일치 |
| `stateBytesAccepted` | pre/post 길이가 각각 1~1,048,576 byte이고 관측 digest가 서명된 이전/다음 head의 stateDigest와 일치 |

[production backend](../../src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit.ts)는
기존 검증에 성공한 뒤에만 이 투영을 구성한다. V1 submit, V2 submit, V2 recovery 세 경로에
연결했다. [gateway](../../src/hswm/effect-runtime/src/canonical-atom-v2-verified-admission-gateway.ts)는
계산된 세 사실을 기존 canonical wire에 넣는다. transient 관측을 저장 형식에 추가하지 않아
이전 wire/commit schema와 canonical 바이트 계약을 유지한다.

[Lean 모델](../../formal/HSWMAdmissionPreflight.lean)은 기존 `verifiedAdmissionKernel`을 재사용한다.
`nativeRecordFromVerified`가 contract/status를 고정하고 verifier의 시간·digest·intent·nonce·
head를 복사한다. `constructedPreflightComputesFacts`는 bounded byte·digest 조건에서 세 사실을
도출하고, `constructedPreflightKernelAccepts`는 nonce freshness·이전 head·같은 lineage의 즉시
후속 head 조건까지 주어졌을 때 기존 kernel의 승인을 도출한다. 출력 승인을 전제로 놓고
동일한 승인을 결론내리는 방향에만 머물지 않는다.

반대 방향도 검증한다. 모델의 승인은 record와 verifier 투영의 정확한 binding, 검사한 시간,
bounded state digest, 정확한 successor 및 nonce 소비를 함의한다. 이것은 decoded 모델의
정리다. Node verifier가 임의 입력에 대해 언제나 참인 결과를 반환한다는 증명은 아니다.

실제 native verifier는 expected bindings·scope·target·revision·정규 envelope/trust bytes,
key policy/epoch·Ed25519 key·authorizer·유효 기간·서명을 검사한다. 이번 변경은 그 검증기를
새 추상 검사기로 대체하지 않는다. 신뢰 스냅샷과 clock은 여전히 caller-relative다.
`stateBytesAccepted`도 signed head에 묶인 bounded bytes를 뜻하며 의미 상태 전이의 증명은 아니다.

## T1: 기존 native 키 검사의 정확한 순서

[새 helper](../../src/hswm/effect-runtime/src/canonical-atom-v2-journal-validation-guards.ts)를
[실제 domain evolution](../../src/hswm/effect-runtime/src/canonical-atom-v2-domain.ts)에 연결했다.
기존 조건·순서·오류 코드·메시지를 보존한다.

1. 기존 상태 키가 중복이면 `STATE_INVALID`.
2. 읽기 집합 키가 중복이면 `READ_SET_INVALID`.
3. 읽기 집합에 상태에서 해소되지 않는 키가 있으면 `READ_SET_INVALID`.
4. 위 세 검사를 통과해야 이후 native 검증을 계속한다.

[Lean read-set 모델](../../formal/HSWMJournalValidation.lean)은 각 거절 조건과 우선순위,
통과의 필요충분조건을 증명한다. 이전 `JournalAdapter.Fresh`의 기존 키 유일성과 추가
읽기 집합 유일성·해소 전제를 이 gate의 통과로 연결한다. command/schema/atom/provenance,
시간, reference 및 Permit의 전체 검증까지 완료한 것은 아니다. key-ID 문자열의 대응은
기존 native identifier와 key encoding 경계를 따른다.

## 실행·커널 검증

새 Lean 정리는 T2 13개, T1 14개, 합계 27개다. 고정 Lean 4.32.1에서 fresh 출력 디렉터리와
`--trust=0`으로 각각 의존 소스 11개·4개를 컴파일했다. 새 정리 전부의 공리 의존성을
확인했고 `EXACT_SOURCE_KERNEL_CHECKED`를 얻었다. 허용 집합은 `Classical.choice`,
`Quot.sound`, `propext`이며 proof hole이나 새 사용자 공리는 허용하지 않는다.
의존 모듈의 모든 정리를 개별 감사했다는 의미는 아니다.

감사기의 lexical precheck가 기존 inductive constructor 이름 `admit`를 proof-hole tactic과
혼동하지 않도록 구분했다. 실제 소스 6개와 `by admit`, case 본문의 `admit` 등 음성 예제를
검사한다. 최종 기준은 fresh kernel compilation과 transitive `#print axioms` 결과다.
Lean은 미완성 증명의 의존성을 `sorryAx`로 드러낸다.
[Lean 공식 증명 검증 문서](https://lean-lang.org/doc/reference/latest/ValidatingProofs/),
[공리 의존성 문서](https://lean-lang.org/doc/reference/latest/Axioms/).

[preflight 대조 검사](../../tests/effect-runtime/admission-preflight.test.ts)는 실제 임시 issuer가
서명한 연속 두 전이에서 production preflight를 추출한다. 새 Lean CLI가 record constructor와
일치함을 확인하고 기존 Admission Kernel CLI와 successor를 대조한다. 두 CLI를 실제 subprocess로
실행한다. verifier binding·시간·길이·digest·nonce·head의 16개 변경은 거절된다. 서명 변조와
pre-state digest 불일치는 실제 native 경로에서 hook 이전에 거절된다.

또한 verifier 투영과 record를 함께 위조하면 decoded 모델에서는 승인될 수 있는 반례를
남긴다. 투영의 내부 일치가 native 인증 성공을 대신할 수 없다는 경계를 실행으로 확인한다.
[read-set 대조 검사](../../tests/effect-runtime/journal-validation.test.ts)는 정상·중복·누락·우선순위
7개 입력을 실제 Lean CLI와 대조한다. 이전 journal adapter/replay, native runtime, 파일 복구,
Permit, process crash, gateway/V2 저장·재시작 검사까지 총 15개 파일 95개 테스트가 통과했다.
TypeScript·Effect 검사, runtime build 및 관련 Lean build도 통과했다.

[검증 기록](artifacts/hswm_native_preflight_refinement_2026-10-07/validation.v1.json)에 정확한
소스·실행 binary·감사 결과·검사 범위를 보존한다. 호스트별 원본 출력은
`.local/preflight-refinement-2026-10-07/`에 보존한다. 새 실제 LLM 호출이나 학습 효능 실험은 없다.

## 그래프와 다음 의무

[후속 진행 bundle](../../ontology/development/HSWM_PREFLIGHT_REFINEMENT_PROGRESS_2026-10-07.v1.json)은
코드 커밋의 source bytes와 T1/T2의 새 관측을 연결한다. 이전 계획·replay·adapter·통합 view는
원래 바이트와 UID를 유지한다. 최신 `progress` 조회와 이전 통합 조회를 모두 보존한다.
현재 상태는 T1 `PARTIAL_READ_SET_VALIDATION_PROVED_REFINEMENT_OPEN`,
T2 `PARTIAL_PREFLIGHT_FACTS_COMPUTED_REFINEMENT_OPEN`이며 두 task 전체 완료는 `OPEN`이다.

다음 T1 의무는 strict command/schema·provenance·reference validation과 JSON decoding 경계의 대응이다.
T2에는 verifier 결과 투영의 외부 의미, actual wire/decoder 대응과 caller trust/time 전제가 남는다.
T3의 OS 게시·장애 모델, 이후 실험 의무는 기존 의존관계를 따른다. PS-3·5·6 미확립과
과거 부정 실험 결과를 승격하지 않는다. 연구 진행 그래프는 canonical 학습 상태가 아니다.

```sh
# repository root
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime run build
HSWM_RUN_SEMANTIC_LEAN=1 npm --prefix src/hswm/effect-runtime test -- ../../../tests/effect-runtime/admission-preflight.test.ts ../../../tests/effect-runtime/journal-validation.test.ts --maxWorkers=1
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile admission-preflight --output NEW_PRIVATE_ADMISSION_DIRECTORY
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile journal-validation --output NEW_PRIVATE_JOURNAL_DIRECTORY
src/hswm/effect-runtime/bin/hswm-workspace query progress current
src/hswm/effect-runtime/bin/hswm-workspace query progress next
```
