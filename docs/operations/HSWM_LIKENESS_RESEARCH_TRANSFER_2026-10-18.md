# HSWM_LIKENESS 연구의 HSWM 흡수

2026-10-18 · `SECONDARY_AI` 구현·연구 연결. 사용자 정본은 기존
[의미론적 연결·구조 최적화 원문](../canon/USER_PRIMARY_HSWM_SEMANTIC_TOPOLOGY_OPTIMIZATION_2026-10-12.md)을 참조한다.

**유한하게 선언한 의미 공간에서 규칙 중복, 의미 변경, 허브 분해의 손실을 검사하는 실행 코드를 HSWM에 추가했다.**
HSWM_LIKENESS의 연구를 아래 다섯 적용 지점에 연결했다. 이번 구현은 자동 W·노드 생성/삭제를
완성한 것이 아니라, 그러한 변경을 평가할 때 사용할 의미 진단이다. 원 연구의 Lean 증명을 새 TypeScript
구현의 증명으로 이전하지 않으며, 이번 작업에서 원 논문·Lean·실모델 실험을 다시 수행하지 않았다.

## 흡수한 내용과 적용 지점

| 연구 | HSWM에 가져온 내용 | 현재 상태·조건 |
|---|---|---|
| 유한 규칙 의미·예외 | 명시한 변수·도메인·역할 판본에 대한 완전 열거, `unless` 의미, 변경 전후 해석 비교 | **구현**. JSON typed program만 해석한다. 자연어→규칙 추출은 하지 않는다. |
| join tree·관계 접합 | 작은 노드로 나눈 뒤 다시 조합했을 때 원래 관계의 허용 해석을 보존하는지 검사 | **구현**. 투영·자연 접합을 완전 열거로 비교한다. 원 연구의 join-tree 알고리즘 이식이나 전체 그래프 비순환성 요구가 아니다. |
| 위상·cohomology·zigzag | 구조 신호와 의미 충돌을 구별하는 진단 조건 | **연결된 연구 조건**. nerve Betti 수, sheaf H¹, 현재 관측의 δx=b 해 존재는 별개다. H¹>0만으로 노드를 삭제하거나 W를 벌점 처리하지 않는다. |
| scoped continual learning v3 | 과제별 갱신이 다른 과제와 예외를 보존해야 한다는 변경 범위 계약 | **기존 연구에 연결**. 계산기 보조/비보조, 학습/추론 개선을 구분한다. v3의 controller rule 언어와 이번 유한 의미 IR은 서로 다른 계약이며 자동 변환하지 않는다. |
| W-learning·outcome loop | E2의 선택을 E4의 실제 결과·평가·채택 정책으로 되돌리는 경로 | **기존 policy bridge에 연결**. 문맥 관련도, 논리적 제약 강도, 측정된 효용 W는 구별한다. 실제 결과가 부족하면 UNKNOWN/no-op을 유지한다. |

join-tree 연구의 국소→전역 확장에는 변수·판본의 정확한 정렬, running intersection,
각 separator 투영의 일치, 비어 있지 않은 국소 관계가 필요하다. 조건 불충족을 UNSAT로 부르지 않는다.
이번 검사기는 최대 4,096개 배정을 열거하므로 join-tree 조건 없이도 **해당 유한 입력**의 분해를 비교할 수 있다.
역할 이름만 같거나 embedding이 가까운 것은 동일 변수·판본이라는 근거가 아니다.

위상 연구에서 삭제가 있는 시간 흐름은 두 complex의 face 합집합을 사용한다. 원시 context들을 먼저
합쳐 새 교차를 만들어내는 방식은 다른 대상이다. 현재 image-overlap 진단을 전체 zigzag barcode로
승격하지 않는다. 13개 이론을 연결한 기존 연구 온톨로지의 제안·가정·계획 상태도 유지한다.

v3의 두 authored Boolean 과제·두 seed에서 계산기 보조 17/32→32/32 결과는
[기존 HSWM 기록](../../F1_R8_RESULTS_LOG.md#scoped-continual-20261018)에 이미 반영되어 있다.
이 문서는 그 결과를 새 실험으로 세지 않는다. observation-only와 비보조 결과, v2의 실패도 유지한다.
OUTCOME_LOOP의 실제 두 요청에서 audit 준비와 유효한 W 갱신은 같지 않았고, UNKNOWN 및 baseline 0 유지가 기록되어 있다.

## 구현 계약

- 순수 검사: `src/hswm/effect-runtime/src/semantic-context-finite-domain.ts`.
- 저장소 연결: `semantic-context-finite-runtime.ts`의 `reviewPlannedFiniteSemantics`.
- CLI: 기존 `hswm-context`의 `finite-review`, 독립 `bin/hswm-semantic-finite`.
- 검증: `tests/effect-runtime/semantic-context-finite.test.ts`.

관계의 `semanticText`에 `hswm-finite-semantic-program/v1` JSON을 명시한다.
변수는 정확한 frame 역할 occurrence의 `roleOrdinal`과 유한 값 목록을 가진다. 이 연결은 **작성자가
선언한 의미 해석**이며 participant 자연어에서 자동 도출한 사실이 아니다. 전체 역할 내용·owner·key·revision을
읽고 source commitment를 보존한다. 제공된 standalone frame의 해시 일치는 실제 저장소 채택의 인증이 아니다.
`hswm-context finite-review`는 현재 admitted store와 plan을 읽어 그 출처를 별도로 명시한다.

```json
{
  "contract": "hswm-finite-semantic-program/v1",
  "variables": [
    {"id": "guard", "roleOrdinal": 0, "values": ["0", "1"]},
    {"id": "required", "roleOrdinal": 1, "values": ["0", "1"]},
    {"id": "exception", "roleOrdinal": 3, "values": ["0", "1"]}
  ],
  "expressions": [
    {"op": "is", "variable": "guard", "value": "1"},
    {"op": "is", "variable": "exception", "value": "1"},
    {"op": "is", "variable": "required", "value": "1"},
    {"op": "unless", "when": 0, "exception": 1, "require": 2}
  ],
  "clauses": [{"id": "rule", "expression": 3}]
}
```

위 예시는 역할 0·1·3이 실제로 해당 participant에 연결된 frame에만 적용한다.
`unless`는 `(guard AND NOT exception) IMPLIES required`다. 예외가 활성화되면 의무를 면제하며,
`required=false`를 강제하지 않는다. 8개 배정 중 `guard=1, exception=0, required=0`만 위반한다.

`not`, `and`, `or`도 지원한다. 표현식 참조는 자신보다 앞선 index만 가리켜야 한다.
쓰이지 않는 표현식, 중복 ID/역할 연결, 알 수 없는 값, null, 초과 필드, 중복 JSON key, 뒤에 붙은 자료는 거절한다.
입력은 stdin 1 MiB, semanticText 8,192 UTF-16 units, 변수 16개·변수별 값 16개,
표현식 128개·clause 32개, 전체 배정 4,096개, factor bag 8개까지다. 한도 초과 시 샘플링·잘림 없이 거절한다.

검사 결과의 의미:

1. **개별 규칙 기여:** 그 clause 하나를 제거하면 새로 허용되는 해석을 witness로 반환한다.
   `REDUNDANT_WITHIN_DECLARED_DOMAIN`은 해당 유한 모형의 논리적 중복이다. 여러 중복 clause를
   동시에 지워도 된다는 뜻이 아니며 출처·책임·다른 과제에서의 기여는 별도다. 모순된 base는 별도 상태로 표시한다.
2. **의미 변경:** 동일 변수·도메인·역할 순서에서 `EQUIVALENT`, `STRENGTHENED`, `WEAKENED`,
   `INCOMPARABLE`을 판정하고 추가·제거된 해석의 개수와 witness를 보낸다.
   여기서 강화는 허용 해석 집합이 좁아졌다는 뜻이다. **W 증가나 지능 개선을 뜻하지 않는다.**
3. **예외 참조:** 변경 후 사라진 exception 변수의 문법적 참조를 따로 보고한다.
   참조가 남았다는 사실만으로 예외 의미 보존을 보장하지 않는다. 그 의미 변화는 해석 집합 비교로 확인한다.
4. **분해:** 원 관계를 각 bag에 투영하고 자연 접합해 새로 생긴 해석을 찾는다.
   세 변수 parity를 쌍별 bag으로 분해하면 4개였던 허용 해석이 8개로 늘어난다.
   `LOSSLESS_WITHIN_DECLARED_DOMAIN`도 역할·권한·출처까지 포함한 노드 병합/삭제 허가는 아니다.

## 실행과 E2↔E4 연결

기존 저장소를 사용하는 `hswm-context` 요청의 `action`을 `finite-review`로 정하고,
`prepare`에서 얻은 현재 `expectedPlanSha256` 및 동일한 `spec`, `durableRoot`, `journalLineageId`,
전체 native `schema`와 다음 필드를 제공한다. 대상 관계는 plan 안에 명시되어야 한다.

```json
{"finiteReview": {
  "relationUid": "relation:door",
  "factorBags": [["guard", "required"], ["guard", "exception"]]
}}
```

`proposedSemanticText`를 추가하면 변경을 비교한다. 이 요청에는 Jev receipt나 LLM cell을 넣지 않는다.
읽기 전후 plan 및 state revision을 대조하고 전체 frame이 문맥 예산을 넘으면 거절한다.
결과는 진단 시점의 snapshot이며 나중 채택할 때 stale/read-set 검사를 대신하지 않는다.

독립 CLI는 기존 native frame codec의 `{kind,payload}`를 받아 동일한 검사를 한다.
`contract`는 `hswm-finite-semantic-review/v1`, `representation`은 `direct_json`, `incidence`,
`role_table` 중 하나다. 입력 파일은 명시적으로 생성한 representation을 사용한다.

```bash
src/hswm/effect-runtime/bin/hswm-semantic-finite --help
src/hswm/effect-runtime/bin/hswm-semantic-finite < request.json
src/hswm/effect-runtime/bin/hswm-context < stored-review-request.json
src/hswm/effect-runtime/bin/hswm-workspace show likeness-transfer
src/hswm/effect-runtime/bin/hswm-workspace query likeness-transfer transfers
src/hswm/effect-runtime/bin/hswm-workspace validate likeness-transfer
```

exit 0은 진단 완료다. 의미 손실·모순 결과도 0이며 결과의 status를 읽어야 한다. 2는 입력/조건 거절,
3은 실행 결함이다. CLI는 canonical state·W를 수정하거나 모델을 호출하지 않는다.

연결 순서는 **E2 문맥 선택 → 실행·독립적으로 평가 가능한 결과 → E4 W 평가 → 변경 후보 → 의미 진단
→ owner의 채택 → 다음 실행**이다. 기존 [context policy bridge](HSWM_CONTEXT_POLICY_BRIDGE_2026-10-11.md)가
결과로 학습한 문맥 정책을 채택·사용하는 경로를 제공한다. 이번 진단은 변경 후보 검토에 연결할 수 있다.
학습이 의도적으로 의미를 바꾸는 경우 동등성만 요구하지 말고 변경 witness와 실제 결과를 함께 판단해야 한다.
Jev 관련도 확률이나 구조 검사 통과만으로 W를 갱신하지 않는다.

아직 남은 실행 범위는 자연어의 유한 추상화 검증, 실제 결과에 근거한 구조 후보 생성,
예외·권한·비용을 포함한 채택, 지속 저장된 revision의 다음 프로세스 사용,
중복 outcome의 중복 갱신 방지 및 같은 예산의 holdout 효능 평가다. 자동 허브 생성·삭제를 구현 완료로 표시하지 않는다.

## 출처 고정과 표준 그래프

2026-10-18에 sibling `HSWM_LIKENESS` 작업 트리를 읽었다. 관측 HEAD는
`6ec3ee6327b59a7bbad9120396e71d92a085b2a9`다. 아래 **미추적 파일은 그 커밋의 내용이라고 주장하지 않는다.**
경로·바이트 길이·SHA-256은 읽은 로컬 자료의 식별자이며, sibling 전체나 생성된 검증 산출물을 복제하지 않았다.

| sibling 상대 경로 | 바이트 | 상태 | SHA-256 |
|---|---:|---|---|
| `docs/CHU_SEMANTICS_2026-10-16.md` | 14000 | 미추적 | `d48e2bac96b92539d361383ac8a05f76bbf17aa25f3ee277957fadedfcecadf7` |
| `tools/chu-semantics/model.mjs` | 9185 | 미추적 | `14628e9309960a8d37d90cf82197bdc3a6b9e01ae82f7a0a8bcd643fee77a804` |
| `docs/CHU_JOIN_TREE_2026-10-16.md` | 10674 | 미추적 | `8c008fafb942a4085b7f777685a2b1534e9550292a3776e3c698461ae5e0a0df` |
| `tools/chu-join/model.mjs` | 7732 | 미추적 | `bdefee3727010a4e59874bd42192af2b7ae7ace639d2b7faf02a07a4dcffca9d` |
| `docs/CHU_TOPOLOGY_RESOLUTION_2026-10-11.md` | 13637 | tracked·clean | `7721011e95aacac373e2db7d2adb9f388eb998b80ccf49c9b1a1507c2956c4a8` |
| `docs/CHU_THEORY_ONTOLOGY_2026-10-15.md` | 9362 | 미추적 | `46dea92ac6435bae3a624dd6b01461bb38575824592ab59196f4bf8955dded8a` |
| `docs/CONTINUOUS_LEARNING_V3.md` | 9444 | 미추적 | `10cbe4fda3061698224bb2a58fb84d360f94f95b06ceaa4f23e8d2605261bea4` |
| `src/continuous-learning-v3.ts` | 8853 | 미추적 | `5457e7cb6c7048d184baa8a2c1d0f1db5404ec3b9e10a21691939a4bc746b71f` |
| `docs/OUTCOME_LOOP.md` | 11546 | 미추적 | `086eec178ba18ba0c61ee32975a275ce9f3439df19f3e91dcbe047d6a31d9573` |
| `docs/W_LEARNING.md` | 30287 | tracked·clean | `4de0202cab125b67d639e81b669c872e081bc082d4ee87808e2027d620c18042` |

작업공간 `likeness-transfer`는 작은 적용 노드에서 원 연구·구현/설계 상태·조건·CLI 사용법으로 연결한다.
기존 E2/E4·사용자 의미 위상 원문은 외부 anchor로 참조하고 변경하지 않는다. native RDF v2 투영,
공통 SHACL, SPARQL을 사용한다. 공유 KG에 대한 쓰기나 사용자 정본의 재정의는 포함하지 않는다.

## 검증 상태

현재 작업 트리에서 관련 4개 suite **36개 테스트**가 통과했다. 새 suite의 12개 테스트는
두 변수의 모든 진리 함수 쌍 256개, 예외 면제, 중복 clause, 모순된 base, parity 분해 손실,
변수/판본 정렬, 입력 거절, native representation commitment, 실제 독립 CLI,
admitted 파일 저장소의 `hswm-context` 읽기와 상태 불변을 확인한다. 기존 context·policy·frame suite도 통과했다.

최초 bulk 임시 공간에서는 새 suite가 11개 통과·1개 content-store I/O 실패였다.
소량의 저장소 fixture를 POSIX 메모리 임시 공간에 두어 36개를 재검사했다.
이 환경 차이를 숨기거나 최초 실행을 전체 통과로 표시하지 않는다.
최종 실행은 관리 실행기의 `--memory-bytes 33554432`와 `STORAGE_MEMORY_TMPDIR`를 사용했고,
종료 시 해당 임시 공간을 정리했다. TypeScript·temporal 타입 검사, Effect/functional lint,
두 native build target, 같은 36개 테스트가 모두 통과했다. Effect allowlist는 변경하지 않았다.

그래프는 **14개 노드·21개 관계·3개 외부 anchor**다. native RDF v2 투영과 공통 SHACL이 통과했고,
SPARQL `transfers`가 다섯 적용 지점의 여섯 출처 연결을 반환했다. Markdown portable math 검사도 통과했다.
이 검증은 유한 모형·읽기 경로·표준 그래프 구조의 공학 검사다. 전체 의미 정렬 증명이나 실제 학습 효능을 뜻하지 않는다.
