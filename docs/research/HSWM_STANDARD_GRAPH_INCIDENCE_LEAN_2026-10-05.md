# 동적 그래프 표현의 Lean 증명

2026-10-05 · `SECONDARY_AI_ENGINEERING_VALIDATION`

HSWM의 기존 RDF 출력에 맞춰, 관계와 참여자 수가 달라지는 그래프의 표현 보존을 Lean 4로
증명했다. [이전 표현 정리](../../formal/HSWMExecutableGraphEncoding.lean)가 고정한 관계 수와
arity를 이번 모델에서는 고정하지 않는다. 선택한 atom 메타데이터와 순서 있는 참조를
왕복 복원하고, 이 모델 위에 주어진 Step과 Learn을 표현 간에 옮겼을 때 모든 유한 실행열의
관측 결과가 보존됨을 보였다. 전체 canonical 상태나 실제 LLM의 구현 증명은 아니다.

## 표준과 기존 계약

[RDF 1.1](https://www.w3.org/TR/rdf11-concepts/#section-Graph-syntax)의 그래프는 triple의
집합이므로 직렬화 문장 순서를 참여자 순서로 사용할 수 없다. 기존 HSWM compiler가
내보내는 관계 atom과 typed reference 노드를 유지하고, 참여자 순서는 명시적인 `ordinal`로
복원한다. 이는 [W3C의 n항 관계 표현 지침](https://www.w3.org/TR/swbp-n-aryRelations/)에
설명된 관계 노드 방식과 연결되지만, HSWM predicate와 ordinal 계약은 프로젝트의 로컬
profile이다. 해당 지침은 Working Group Note이며 HSWM 전용 표준 인증이 아니다.

기존 RDF 1.1, N-Quads 및 [SHACL 1.0](https://www.w3.org/TR/shacl/) 경로를 재사용했다.
production compiler, schema, shape, 표준 profile과 외부 의존성은 변경하지 않았다.
SHACL 검사는 실제 기존 engine으로 실행했으며, 구조 검사의 통과를 과학적 진실이나 승인
권한으로 해석하지 않는다. 새 데이터베이스나 KG writer는 추가하지 않았다.

질문과 계약은 다음과 같다.

| 질문 | 기존 그래프 계약 | 이번 증명 또는 검사 |
| --- | --- | --- |
| atom 버전을 구별할 수 있는가 | canonical key는 schema, lineage, UID, revision을 구분 | Lean에서는 key 문자열을 불투명한 식별자로 취급. wire 중복 key 거절 및 실제 RDF IRI 대응 검사 |
| 누가 어떤 역할로 관계에 참여하는가 | `hasTypedReference`는 atom → reference, `sourceAtom`은 reference → atom, `targetAtom`은 reference → target atom | source별 참여 행의 역할·참조 타입·대상을 복원하고 양방향 연결과 endpoint 존재 확인 |
| 같은 대상을 여러 역할로 가리킬 수 있는가 | reference identity는 source와 ordinal. role과 referenceType은 별도 값 | 순서와 중복 대상을 보존. 동일 typed reference 전체의 중복은 기존 canonical validator가 여전히 거절 |
| 참여 행은 어떻게 유일하게 복원하는가 | 각 행에 source, target, type, role, ordinal 하나씩. source별 ordinal은 0부터 연속 | `RowsAt`, `rowsValid_iff`, 누락·중복·잘못된 ordinal 거절 |
| 어떤 출처와 소유자 정보가 보존되는가 | owner 문자열, content descriptor, provenance mode, evidence digest, 선택적 provenance source | 해당 필드의 정확한 복원. owner의 실제 권한과 evidence의 진실성은 별도 |
| 표준 그래프에서 canonical 상태로 쓸 수 있는가 | 기존 `writeBack: FORBIDDEN` | 새 CLI는 비교 보고만 수행하며 `admissionProved`와 `fullCanonicalStateProved`는 항상 false |

`role:context`와 `role:exception`도 순서 있는 역할 값으로 보존한다. 원문 semantic payload
내의 예외 목록까지 이 RDF 메타데이터에 들어 있다고 가정하지 않는다. 전체 그래프의
acyclicity도 요구하지 않는다. 참조 방향, 역할과 식별자 보존이 여기서의 조건이다.

## Lean에서 증명한 범위

[HSWMStandardGraphIncidence.lean](../../formal/HSWMStandardGraphIncidence.lean)에 보조정리를
포함한 정리 24개를 추가했다.

- **표현 왕복과 식별:** native view를 incidence view로 바꾼 뒤 복원하면 원래 view와 같다.
  반대 방향은 source·ordinal이 정합적이고 orphan 행이 없는 정규화된 graph에 대해 성립한다.
  따라서 이 view의 서로 다른 상태는 인코딩으로 합쳐지지 않는다.
- **유한 검사 범위:** source atom, header, row source를 모두 포함하는 key 집합을 검사하고
  그 밖에 값이 없음을 확보하면, 검사한 전체 view의 정확한 복원을 도출한다.
  wire의 중복 key 거절과 완전한 key 집합 구성은 CLI 및 테스트 연결부의 의무다.
- **참조와 변경:** 참조 길이, 역할·대상 목록, 서로 다른 slot의 구별을 보존한다.
  주어진 schema domain/range predicate의 충족 여부도 왕복 복원으로 보존된다.
  한 key의 삽입·교체·삭제는 표현 간에 대응하고 다른 key 값은 유지된다.
- **실행과 학습:** 이 view 위에 명시적으로 주어진 결정적 Step/Learn을 옮기면 guard,
  거절 사건, 관측 출력, 최종 상태가 모든 유한 사건열에서 대응한다.
  관계 수와 arity가 변해도 같은 정리가 적용된다.

함수형 Store는 일반적인 key 조회 모델이며, 유한 runtime snapshot은 그 한 사례다.
유한 support가 주어지면 encoding이 이를 보존하지만, 임의의 Dynamics가 영원히 유한한
상태만 생성한다고 추가로 증명한 것은 아니다. 옮긴 Dynamics는 수학적으로 구성한 해석기다.
현재 production RDF 경로가 Step/Learn을 실행하거나 canonical write를 허용한다는 뜻은 아니다.

## 실제 RDF와 연결한 검사

[대조 테스트](../../tests/effect-runtime/standard-graph-incidence.test.ts)는 기존 schema validator,
journal builder와 RDF compiler로 만든 N-Quads를 N3로 읽는다. 검증할 header와 participation은
실제 RDF 문장에서 추출하며, manifest에 보관된 native state를 복사하지 않는다. 원본 atom에서
별도로 만든 기대 view와 [Lean CLI](../../formal/HSWMStandardGraphIncidenceCli.lean)를 대조한다.

참여자 수 1·2·3·4, atom 수 4·5·6·7인 서로 다른 snapshot과 RDF 문장 순서를 뒤집은 사례를
확인했다. 이는 여러 유효한 synthetic snapshot의 대조이며, 실제 모델이 학습으로 topology를
변경했다는 실행 기록은 아니다. 같은 RDF triple의 재등장은 집합 의미론에 따라 중복 제거한다.
서로 다른 역할로 같은 target을 가리키는 participation은 유지한다.

Lean 비교 26건 중 정상 5건은 통과했고, 메타데이터·역할·참조 타입·대상·출처·ordinal 변경,
누락·중복·orphan을 포함한 변조 21건은 거절했다. 음수 ordinal의 wire decoding도 거절했다.
별도로 실제 RDF의 datatype, named graph, participation identity와 연결을 손상시킨 5건을
거절했다. 원래 fixture에는 기존 SHACL shape를 실행해 통과를 확인했다.

## 검증 결과와 재현

Lean 4.32.1에서 library와 CLI build가 통과했다. 새 audit profile `standard-graph-incidence`는
import closure 2개를 새로 컴파일하고, 새 정리 24개의 공리 의존성을 검사했다.
`sorry`, `admit`, `native_decide`, 새 사용자 공리는 없고 관측된 의존성은 `propext`,
`Quot.sound`다. 감사 상태는 `EXACT_SOURCE_KERNEL_CHECKED`다. dependency 파일 전체의
모든 정리를 이번에 개별 감사했다는 뜻은 아니다.

관련 테스트 6개 파일의 20개 사례, TypeScript·temporal·Effect·functional 검사와 runtime build가
통과했다. 기존 RDF·SHACL·hypergraph 검사와 이전 preflight 대조도 포함했다. 새로운 library와
CLI를 Lake의 기본 build target에도 등록했다. 전체 테스트 suite와 외부 표준 적합성 suite를
다시 실행한 결과는 아니다.

```bash
# cwd: formal
lake build HSWMStandardGraphIncidence HSWMStandardGraphIncidenceCli

# cwd: HSWM root
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime run build
HSWM_RUN_SEMANTIC_LEAN=1 npm --prefix src/hswm/effect-runtime run test -- ../../../tests/effect-runtime/standard-graph-incidence.test.ts ../../../tests/effect-runtime/canonical-atom-v2-hypergraph-projection.test.ts test/canonical-atom-v2-rdf-projection.test.ts test/native-hypergraph-shacl.test.ts ../../../tests/effect-runtime/semantic-philosophy-proof-process.test.ts ../../../tests/effect-runtime/graph-loop-preflight.test.ts --maxWorkers=1
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile standard-graph-incidence --output NEW_PRIVATE_DIRECTORY
```

## 다음 증명 경계

현재 RDF 출력은 원문 payload, lifecycle, 전체 schema 제약, bootstrap·accepted-transition 정보와
전체 journal을 담지 않는다. 따라서 이번 결과는 **선택한 메타데이터 view의 무손실성**이다.
canonical 전체 상태의 무손실성, RDF parser의 보편적 정확성, IRI encoding·해시 계산의 정제,
실제 authorization·CAS·crash recovery, LLM 효과와 HSWM 전체 완성은 별도 미해결 의무다.

다음 형식 작업은 이 view에 빠진 canonical 상태를 보존하는 명시적 확장 계약과, 실제 승인
전이가 그 계약을 유지하는지의 증명이다. 이전 [전역 revision 반례](HSWM_GRAPH_LOOP_PREFLIGHT_2026-10-05.md)는
계속 유효하다. 여기의 국소 표현 갱신 정리를 동시 commit의 독립성으로 바꾸어 주장하지 않는다.
HSWM-likeness 점수를 재산정하거나 기존 `GAPS_REMAIN` 판정을 승격하지 않았다.
