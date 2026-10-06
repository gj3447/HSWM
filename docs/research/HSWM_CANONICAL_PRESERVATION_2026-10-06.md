# Canonical 상태 보존과 승인 조건의 Lean 증명

2026-10-06 · `SECONDARY_AI_ENGINEERING_VALIDATION`

HSWM의 기존 RDF·SHACL 경로에 이어, 원본 canonical 상태를 보존하는 조건을 실제 v2 전이의
필수 후조건으로 추가했다. 기존 atom 버전을 유지하면서 새 버전만 추가하고, schema와 이력의
연속성을 확인한다. 검사 실패는 `STATE_PRESERVATION_FAILED`로 반환되어 canonical 커밋을
막는다. Lean 4에서는 이 조건과 조건부 승인 모델을 증명했고, 실제 저장소와의 연결은 실행
테스트로 확인했다. 전체 HSWM이나 TypeScript 구현 전체의 형식 증명은 아니다.

## 표준 그래프와 원본 상태

[기존 표준 그래프 검증](HSWM_STANDARD_GRAPH_INCIDENCE_LEAN_2026-10-05.md)은 실제 RDF 1.1,
N-Quads와 SHACL 경로에서 선택한 메타데이터와 순서 있는 참여 관계를 검사한다. HSWM의
predicate, identity와 승인 정책은 프로젝트의 계약이다. 표준 형식 사용 자체가 원본 상태
전체의 보존이나 쓰기 권한을 보장하지는 않는다.

이번 계약은 원본 전이에 적용한다. RDF 출력에서 빠진 lifecycle, 전체 schema 제약,
bootstrap 상태와 accepted-transition 이력을 포함하며, RDF profile을 확장하거나
`writeBack: FORBIDDEN`을 변경하지 않는다. 기존 그래프의 표현 보존 증명과 원본 전이의
보존 증명은 각각의 명시된 범위에서 함께 사용한다.

## 보존 계약

[순수 검사기](../../src/hswm/effect-runtime/src/canonical-atom-v2-preservation.ts)는 검증된 native
값을 받아 다음 조건을 확인한다.

| 대상 | 허용되는 전이 |
| --- | --- |
| schema | 버전과 전체 schema 값 유지. 일반 v2 전이는 schema migration을 허용하지 않음 |
| 기존 atom | key와 전체 envelope 유지. owner, lifecycle, provenance, content descriptor, 순서 있는 참조 포함 |
| 새 atom | 비어 있지 않은 writes의 정확한 추가. 기존 key와 겹침, 중복 key, 누락과 추가 외 atom 거절 |
| revision | 예상 revision이 현재 값과 일치하고 정확히 1 증가. JavaScript 안전한 정수 범위 유지 |
| bootstrap | 승인 이후 닫힘. 이미 닫힌 상태의 재개방 불가 |
| 승인 이력 | 기존 순서를 유지하고 처음 보는 transition ID 하나만 끝에 추가 |

envelope와 schema는 해시 대신 전체 정규화된 JSON 텍스트로 비교한다. 모든 객체의 필드 이름을
정렬하고 배열 순서는 유지한다. 객체 필드의 삽입 순서는 값의 의미에 영향을 주지 않지만,
참조 배열의 역할·대상 순서는 보존 대상이다. atom을 나열하는 저장 배열의 순서 자체는
이 계약의 보존 대상이 아니며 기존 domain이 별도로 정렬한다.

이 텍스트는 비교를 위한 로컬 표현이다. 기존 canonical JSON byte protocol이나 원래 파일의
바이트열과 동일하다는 주장은 하지 않는다. native snapshot 함수를 거치므로 타입에 없는
미지의 필드를 보존하는 계약도 아니다. 입력의 구조 검증과 key 인코딩의 정확성은 기존
validator 및 adapter의 의무다. content descriptor 보존은 payload 바이트의 영구 가용성과
동일하지 않다.

## 실제 승인 경로

[evolveValidatedCanonicalAtomsV2](../../src/hswm/effect-runtime/src/canonical-atom-v2-domain.ts)가
기존 schema·참조·revision·provenance 검사를 마치고 후보 상태를 만든 직후 이 후조건을
검사한다. durable runtime에서는 후보 생성이 journal publication보다 앞서므로 보존 실패를
canonical 상태에 반영하지 않는다. journal의 생성과 replay도 같은 domain 경로를 사용한다.
일반 전이 API는 하나의 고정 schema를 받으므로 production 후조건도 그 schema를 사용한다.
비교 adapter는 서로 다른 두 schema 입력을 받아 변경 여부를 검사할 수 있다.

기존 grant, graph-loop 검증, content binding과 CAS 검사는 계속 필요하다. Lean의
`authorized`와 `structurallyValid`는 외부에서 공급한 의무의 모델이며 실제 자격 증명이 아니다.
[비교 CLI](../../formal/HSWMCanonicalPreservationCli.lean)의 `approvedUnderSuppliedFlags`는 이
가정 아래의 결과이고, `permissionProved`와 `physicalAtomicityProved`는 항상 false다.
이 CLI는 canonical 상태를 수정하지 않는다.

## 증명과 실행 검증

[Lean 모델](../../formal/HSWMCanonicalPreservation.lean)은 보조정리를 포함한 정리 29개를 담는다.
한 승인 전이가 기존 envelope와 schema를 유지하고, revision과 이력을 정확히 확장함을
증명한다. 권한·구조·보존 조건 중 하나가 실패하면 모델의 상태는 그대로다.
`finite_run_extends_native`는 승인과 거절을 섞은 임의의 유한 실행열에 대해 기존 atom,
schema와 schemaVersion 보존, revision의 비감소, 닫힌 bootstrap 유지, 기존 이력의 prefix
보존을 증명한다. 여기서 envelope와 schema 텍스트는 불투명한 값이며 JSON encoder의
보편적 정확성은 정리의 결론에 포함되지 않는다.

[실행 테스트](../../tests/effect-runtime/canonical-preservation.test.ts)는 실제 파일 저장소와
graph-loop를 통해 초기화와 scripted semantic revision을 커밋한다. 기대 writes는 저장된
envelope와 receipt에서, 비교 schema는 저장된 schema에서 읽는다. 이후 저장소를 다시 열어
전체 durable snapshot과 journal history가 같은지 확인한다. 실제 외부 모델 호출은 없다.

Lean CLI와 TypeScript 검사기의 대조 33건에서 정상 3건은 통과했고, 변조 28건은 거절됐다.
나머지 2건은 보존 조건을 만족해도 공급된 권한 또는 구조 검증 플래그가 false여서 승인되지
않았다. 음수 revision의 wire decoding도 거절했다. 별도 fault injection에서는 production
보존 검사 실패로 canonical state와 history가 유지되고 graph-loop에 거절 사유가 남았다.
staged content와 제어 로그까지 전혀 쓰지 않는다는 뜻은 아니다.

Lean 4.32.1에서 library와 CLI build가 통과했다. 새 `canonical-preservation` audit profile은
정확한 소스를 별도 출력 디렉터리에서 `--trust=0`으로 다시 컴파일하고 정리별 공리 의존성을
검사했다. 상태는 `EXACT_SOURCE_KERNEL_CHECKED`, 관측된 공리는 `propext`, `Quot.sound`다.
`sorry`, `admit`, `native_decide`와 새 사용자 공리는 없다. 로컬 감사 기록은
`.local/graph-preservation-2026-10-06/lean-verification.v1.json`에 있다.

관련 테스트는 13개 파일의 79개 사례가 통과했다. 기존 domain, content runtime, durable
runtime, journal, graph-loop, RDF·SHACL, preflight, lifecycle 연결 검사를 포함한다.
TypeScript·temporal·Effect·functional 검사와 runtime build도 통과했다. 전체 suite나
외부 표준 적합성 suite를 새로 실행한 결과는 아니다.

## 재현과 남은 경계

```bash
# cwd: formal
lake build HSWMCanonicalPreservation HSWMCanonicalPreservationCli

# cwd: HSWM root
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime run build
HSWM_RUN_SEMANTIC_LEAN=1 npm --prefix src/hswm/effect-runtime test -- ../../../tests/effect-runtime/canonical-preservation.test.ts --maxWorkers=1
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile canonical-preservation --output NEW_PRIVATE_DIRECTORY
```

현재 형식 경계에는 payload 바이트 보존·가용성, 전체 journal의 암호학적 연결과 원자성,
실제 권한 검증의 정제 증명, JSON·key adapter의 보편적 정확성과 LLM의 효과가 남아 있다.
실제 runtime의 연결 검사를 이러한 보편 증명으로 승격하지 않는다. 보존 검사는 전이와
replay에 정규화·비교 비용을 추가하며 대규모 성능은 이번 검증 대상에 포함되지 않는다.
기존 HSWM-likeness 점수와 `GAPS_REMAIN` 판정은 유지한다.
