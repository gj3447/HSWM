# Payload 보존과 journal 승인 조건의 Lean 증명

2026-10-06 · `SECONDARY_AI_ENGINEERING_VALIDATION`

[canonical 상태 보존 계약](HSWM_CANONICAL_PRESERVATION_2026-10-06.md)에 이어, 실제 참조 grant
판정과 바이트 비교, journal 게시 사전 검사를 순수 함수로 분리하고 Lean 4 모델과 대조했다.
불변 content store와 원자적인 journal 슬롯 게시를 모델의 연산으로 두었을 때, 기존 payload
바이트와 journal prefix가 보존됨을 증명했다. 실제 파일 저장소에서는 권한 거절, 재열기,
14개 중단 지점과 독립 프로세스 경쟁을 검증했다. OS의 원자성이나 서명의 진위를 전제 없이
증명한 결과는 아니다.

## 실제 코드와 형식 모델의 연결

[durable guards](../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-guards.ts)는
실제 content authorizer와 content file store, journal file store가 호출한다. 기존 판정
순서, 오류 사유와 게시 절차를 유지했다. 사전 검사 통과 이후의 경쟁은 기존 no-replace
hard link와 복구 절차가 계속 처리한다. RDF·SHACL profile과 canonical write 권한은 변경하지
않았다.

| 경계 | Lean에서 증명한 것 | 실제 구현과 대조한 것 |
| --- | --- | --- |
| 참조 grant | 허용 결과와 정확히 일치하는 grant의 존재가 동치. schema 해시, 권한 참조, schema 버전과 scope가 한 grant에 일치해야 함 | production authorizer의 허용·거절 사유, 실제 graph-loop에서 잘못된 권한 참조·scope의 거절과 원래 상태 유지 |
| payload 바이트 | 비어 있는 key에만 저장하는 연산은 기존 바이트를 유지. 같은 key의 다른 바이트는 충돌. 유한 번 저장해도 기존 값 유지 | 호출·반환 버퍼의 변경으로 저장 값이 바뀌지 않음, 정확한 재시도, 이미 점유된 digest 경로의 다른 바이트 덮어쓰기 거절 |
| journal | 정확한 predecessor와 다음 revision 요구. 이미 점유된 슬롯은 덮어쓰지 않음. 원자적 게시 모델의 결과는 이전 prefix 또는 정확한 한 건 추가 | 실제 native journal 바이트로 사전 검사·재시도·충돌 대조, 모든 중단 지점의 복구·재시도, 독립 프로세스 간 단일 승자 |
| 결합 | 공급된 구조 검증, 실제 grant 판정과 기존 canonical 보존 조건을 만족하는 조건부 commit 모델이 native 상태·content·journal 보존 | 동일한 실제 graph-loop commit에서 native 기록과 이전 payload·envelope 바이트를 읽고, 재열기 후 다시 일치 확인 |

참조 grant는 현재 로컬 runtime의 권한 규칙이다. `actorClaim`의 변경만으로 grant 결과가
바뀌지 않는 것도 대조했다. 이 문자열은 인증된 사용자 신원을 증명하지 않는다. 입력
schema 및 grant 구성의 구조 검증은 기존 validator가 담당하며, 판정 함수의 부정 사례에는
구성 단계에서도 거절될 입력이 포함된다. 서로 다른 grant의 일부 필드를 조합해서 새로운
권한을 만들어낼 수는 없다.

## 보존 정리의 범위

[HSWMDurablePreservation.lean](../../formal/HSWMDurablePreservation.lean)에 보조정리를 포함한
정리 32개를 추가했다. byte는 `UInt8`의 리스트로 비교하고, descriptor는 media type,
길이와 digest를 모두 비교한다. 해시의 일치로 바이트의 동일성을 추론하는 공리는 추가하지
않았다. 불변 store에서 같은 이름에 서로 다른 바이트를 쓰려는 시도는 원래 값을 유지한다.
실제 SHA-256 계산의 정확성과 충돌 저항성을 증명한 것은 아니다.

`reference_grant_allowed_iff`는 일치하는 실제 grant의 존재를 요구한다.
`finite_staging_retains_bytes`는 유한 저장열에서 이전 바이트를 유지한다.
`competing_publication_cannot_overwrite`는 같은 슬롯의 승자가 존재하면 후속 게시가 그 기록을
바꾸지 못함을 보이고, `finite_publication_preserves_prefix`는 유한 게시열 전체의 기존
journal prefix 보존을 보인다. `retained_atom_keeps_payload`는 이전 atom과 그 payload의
바인딩이 주어지면 두 보존 정리를 연결한다.

`finite_conditional_commits_preserve_snapshot`은 기존 canonical 보존 정리와 참조 grant 판정,
journal 모델을 결합한다. 거절 시 native 상태와 journal은 그대로이고, 승인 시 기존
envelope, schema, 이력과 content를 유지한다. 이 모델의 commit은 이미 준비된 content를
사용한다. 새 payload의 준비와 가용성은 별도의 content store 검증 의무이며, journal JSON의
decoded native 상태·receipt·descriptor 대응은 adapter의 의무다. 결합 모델 전체가
TypeScript interpreter와 동일하다는 보편적 정제 증명은 아직 아니다.

`publishAtomic`은 원자적인 슬롯 게시를 명시적으로 모델링한다. `crashObservation`은 그
원자적 지점 전후를 관측한다. 이 정의에서 부분 기록이 관측되지 않는다는 정리가 나오지만,
실제 POSIX와 저장 장치가 그 정의를 구현한다는 결론까지 자동으로 나오지는 않는다.
지속적인 외부 파일 변조, 전체 tail 삭제의 탐지, 전원 손실 후의 하드웨어 내구성은 별도
전제와 증거가 필요하다. 기존 rollback 비보장 범위도 유지한다.

## 실행 대조와 검증 결과

[새 테스트](../../tests/effect-runtime/durable-preservation.test.ts)의 Lean 대조는 총 53건이다.
grant 10건, byte 비교 20건, journal 사전 검사 9건, 중단 관측 14건에서 TypeScript와 Lean의
결과가 일치했다. byte 값 256과 음수 revision의 wire decoding도 거절했다.
[Lean CLI](../../formal/HSWMDurablePreservationCli.lean)는 비교 결과만 반환하며,
`canonicalPermitProved`와 `physicalAtomicityProved`는 항상 false다.

테스트는 실제 graph-loop로 초기 상태와 새 atom을 커밋하고, bounded read-only recovery로
journal 기록을 얻는다. 기존 atom의 payload와 envelope를 전부 읽어 커밋 전후 및 fresh
Layer 재열기 후 비교한다. 잘못된 권한 참조와 scope는 각각 `NOT_GRANTED`, `SCOPE_DENIED`로
거절되며 canonical snapshot과 journal history는 변하지 않는다. 제어 로그와 staged content는
추가될 수 있다. 외부 모델 호출은 없다.

journal의 사전 검사 9건은 실제 파일 저장소의 결과와도 대조한다. 최신 기록뿐 아니라 나중
기록이 있는 상태에서 이전 슬롯의 정확한 재시도도 `AlreadyCommitted`로 처리한다.
14개 중단 지점 중 slot link 전 9건은 이전 prefix, link 이후 5건은 정확한 successor를
복구했다. 이후 재시도는 각각 `Committed` 또는 `AlreadyCommitted`였으며 결과 바이트는
동일했다. 이 중단은 테스트용 호출 중단이며 실제 전원 차단 실험이 아니다.

기존 독립 프로세스 경쟁 테스트 2건도 통과했다. 다른 바이트로 경쟁하면 한 승자만 기록되고,
동일 바이트로 경쟁하면 `Committed`와 `AlreadyCommitted`로 수렴했다. 별도 관측 프로세스가
실제 hard link와 정확한 기록을 확인했다.

관련 14개 파일의 테스트 108개, runtime의 TypeScript·temporal·Effect·functional 검사와
build가 통과했다. 새 테스트를 보강한 뒤 해당 파일도 다시 검증했다. 전체 suite와 외부
표준 적합성 suite를 새로 실행한 결과는 아니다.

Lean 4.32.1에서 library와 CLI를 build했다. `durable-preservation` audit profile은 의존
소스 2개를 별도 경로에 `--trust=0`으로 다시 컴파일하고 새 정리 32개의 공리 의존성을
검사했다. 상태는 `EXACT_SOURCE_KERNEL_CHECKED`이며 관측된 공리는 `propext`, `Quot.sound`,
`Classical.choice`다. `sorry`, `admit`, `native_decide`와 새 사용자 공리는 없다. 이전 canonical
보존 모듈은 같은 hash로 다시 컴파일했으며, 그 모듈의 모든 정리를 이번 profile에서 개별
재감사한 것은 아니다. 로컬 기록은 `.local/durable-preservation-2026-10-06/lean-verification.v1.json`이다.

## 재현과 남은 의무

```bash
# cwd: formal
lake build HSWMDurablePreservation HSWMDurablePreservationCli

# cwd: HSWM root
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime run build
HSWM_RUN_SEMANTIC_LEAN=1 npm --prefix src/hswm/effect-runtime test -- ../../../tests/effect-runtime/durable-preservation.test.ts --maxWorkers=1
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile durable-preservation --output NEW_PRIVATE_DIRECTORY
```

다음 정제 경계는 journal JSON·receipt·native replay의 보편적 대응, POSIX 게시·동기화와
추상 원자적 단계의 연결, 서명 검증 및 trusted-key 정책과 canonical Permit의 연결이다.
기존 관련 형식 모듈이 제시하는 외부 증거 조건을 실제 구현이 충족하는지까지 연결해야 한다.
이번 결과를 HSWM 전체 증명이나 LLM 효과로 해석하지 않으며, 기존 HSWM-likeness 점수와
`GAPS_REMAIN` 판정은 변경하지 않는다.
