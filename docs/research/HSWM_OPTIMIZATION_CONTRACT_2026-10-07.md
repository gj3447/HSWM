# HSWM 여섯 최적화 원칙의 비교·보존·병목 계약

2026-10-07 · 사용자 기대와 구축 요청은 `USER_PRIMARY`, 보강 문구·측정 설계는
`SECONDARY_AI`. [사용자 원문](../canon/sources/USER_PRIMARY_HSWM_OPTIMIZATION_REINFORCEMENT_2026-10-07.txt)을
그대로 보존한다. 발화의 정확한 시각은 미상이며 기록일과 구분한다.

사용자는 이렇게 구성한 CHU가 병목 없이 완전히 최적화된 지능이 될 것이라는 기대를
밝히고 원칙 보강과 표준 그래프 구축을 요청했다. 이 기대는 목표·가설로 귀속한다.
현재 측정 결과나 최적성 정리로 바꾸지 않는다. 여섯 원칙은 유지하며, 작업별 보강 본문을
[OPTIMIZATION_EVALUATION.md](../agent-rules/OPTIMIZATION_EVALUATION.md)에 분리했다.

## 여섯 원칙의 보강

| 원칙 | 추가로 구체화한 판정 기준 |
|---|---|
| R1 작업 조건부 활성화 | 선택 규칙의 의존 조건·예외를 함께 읽는다. 작업 변경이나 근거 부족을 확인하면 필요한 원문 범위로 돌아간다. 정적 라우팅과 결과로 학습된 선택은 별도 상태로 기록한다. |
| R2 CLI 중심 실행 | 기존 CLI를 기본 인터페이스로 재사용하되, 성공 종료·실패·시간 초과와 실제 부수효과를 구별한다. CLI라는 형식 자체를 지능의 필요조건이나 성능 근거로 삼지 않는다. |
| R3 사용법의 그래프 결속 | 안정된 명령 식별자와 구현·버전·입출력·실행 조건을 연결한다. 실행 파일이나 사용법이 바뀌면 해당 범위의 결속을 다시 확인한다. |
| R4 컨텍스트 단위 분할 | 과제와 자원 예산을 선언하고, 독립 선택 가능한 의미·책임을 기준으로 분할한다. 정보와 예외 보존, 실제 읽기량, 조합 비용을 함께 비교한다. |
| R5 선택적 연결 | 중간 노드가 줄인 반복과 추가한 탐색·대기 비용을 함께 측정한다. 단계별 비용 감소와 요청 전체의 지연·처리량 개선을 구별한다. |
| R6 의미 기여에 따른 재구성 | 표현 변경은 선언한 관측 범위의 동작 보존과 비용으로, 의미·웨이트 변경은 독립적인 결과와 후속 판단 변화로 평가한다. 현재 답이 같다는 이유만으로 자동 병합하지 않는다. |

원문·기존 여섯 원칙·사용자와 AI의 귀속은 보존한다. 추가 문구는 기존 규칙의 구체화이며
새 승인 절차나 canonical runtime의 실행 허가 조건을 추가하지 않는다.

## 같은 크기에서의 비교

‘같은 지능’은 비교의 성과를 미리 같다고 가정하는 조건으로 사용하지 않는다. 같은
기반 모델과 같은 자원 제약을 가진 CHU의 성과가 달라지는지 관측한다는 **AI 비교 설계**다.
사용자의 CHU 정체성이나 ‘크기’의 최종 정의를 대신 확정하지 않는다.

각 비교는 필요한 항목을 `FIXED`, `MEASURED`, `OUT_OF_SCOPE`로 명시한다. 미정 값은
`UNKNOWN`으로 남기고, 크기 동일성이나 개선을 확정하지 않는다.

| 항목 | 기록할 비교 조건 |
|---|---|
| 과제 | 입력 범위, 성공 기준, 예외, 과제 분포 또는 고정 평가 집합, 허용 오류 |
| 계산 | 기반 모델·설정, 컨텍스트 한도, 호출·토큰·계산 예산 |
| 상태 | CHU 동일성 계보, 상태 용량, 활성 노드·관계 예산 중 고정한 항목 |
| 실행 환경 | 동시성·요청 부하, 저장소·도구 버전, 관측 시간 범위 |
| 성과 | 정답·과제 성공률, 실패·누락률, 전체 지연·처리량, 총비용 |

그래프 노드 수는 표현 크기의 한 지표다. 분할·병합으로 노드 수가 바뀌어도 CHU 자원
용량이나 능력이 같은 비율로 변한다고 가정하지 않는다. 비용에는 선택·조합·모델 추론·
도구 호출·저장·평가와 재시도 등 선언한 범위를 포함한다. 오프라인 재구성 비용을 제외한
경우는 제외 사실과 상각 범위를 적는다.

개선 판단 전 기준선과 평가 범위, 중요 지표, 허용하는 품질·비용 변화 및 불확실성
처리를 정한다. 반복해 조정한 입력의 성과와 분리된 평가 결과를 구별한다. 지연이
줄어도 정확도나 필수 동작이 손상됐다면 그 손실을 함께 보고한다. 측정하지 않은 비용이나
실패를 0으로 채우지 않는다. 이 비교 기록은 기존 실험 근거를 사용하며 별도 승인 장부를
요구하지 않는다.

## 병합과 학습의 서로 다른 조건

**표현 재구성**은 이름 변경·분할·병합·연결의 정리다. 지정한 작업 계약에서 출력,
허용·거부, 역할·예외·출처, 관측 가능한 부수효과와 후속 상태·학습 동작을 보존하는지
확인한다. 적용 범위 밖에서 동치라고 확대하지 않는다. 정보 손실 또는 동작 보존 여부가
불명확하면 병합 효과를 미확정으로 남기고 이전 표현으로 돌아갈 수 있는 계보를 유지한다.

**의미·웨이트 변경**은 의도적으로 이후 판단을 바꾼다. 변경 전 선택과 사용 근거,
관측 결과, 후보 revision과 다음 실행의 변화를 연결하고, 독립 평가로 효용을 확인한다.
이는 동작 보존과 별개의 주장이다. 출처 보존이나 결과 귀속 같은 공통 제약은 유지하며,
파일에 적힌 규칙 선택만으로 learned W나 지속 학습이 구현됐다고 판정하지 않는다.

[기존 Lean 모듈](../../formal/HSWMOperationalQuotient.lean)의
`output_equivalence_does_not_imply_operational_equivalence`는 출력 동치만으로 허용·거부
동치가 보장되지 않는 예를, `visible_bit_has_no_exact_learning_abstraction`은 현재 보이는
비트만 남기면 후속 학습을 보존할 수 없는 예를 다룬다. 주어진 결정적 Dynamics와
관측 인터페이스 아래의 기존 결과이며, 이번 작업에서 새로 증명하거나 자연어 의미 전체에
적용한 것은 아니다. 출처를 해시로 결속하며 이 조건부 범위를 유지한다.

## 병목을 다루는 방법

조회·라우팅, 입력 조합, LLM 추론, 도구 I/O, 그래프 저장, 학습·평가의 여섯 구간을
관측 대상으로 구분한다. 구간별 처리 시간·대기 시간·자원 사용량과 요청 전체의 지연·
처리량·오류를 같은 부하에서 확인한다. 겹쳐 실행된 구간의 시간이나 각 구간 p95를
단순 합산해서 전체 지연으로 사용하지 않는다. 실제 의존 경로와 요청 전체 관측을 사용한다.

한 구간을 개선하면 다른 구간이 전체 처리량을 제한할 수 있으므로 병목 위치를 다시
확인한다. 노드 분할이나 느슨한 연결만으로 모델 추론·I/O 대기·쓰기 충돌의 비용이
사라진다고 가정하지 않는다. 이 구조는 병목을 찾아 줄이는 수단을 제공한다.

‘병목 없음’은 유한 측정으로 모든 과제·부하에서 단정하지 않는다. 관측된 과제·부하와
정한 지연·오류·자원 기준 안에서 미충족 병목이 관측됐는지를 보고한다. ‘완전 최적화’의
증명에는 목적함수, 허용 구조·알고리즘, 자원 제약과 비교 범위를 먼저 정해야 한다.
그 범위를 정의하고 증명하거나 측정하기 전에는 사용자 기대가 달성됐다고 기록하지 않는다.

이번에 **실제 CHU·모델 성능 측정은 수행하지 않았다.** 단계별 측정값은 미측정으로
남는다. 지침·내용 그래프·구조 검증을 성능 측정과 분리한다.

## 표준 그래프에서 읽기

추가 view `optimization-contract`는 여섯 보강 항목, 네 비교 계약, 여섯 병목 관측 구간,
두 기존 Lean 참조, 사용자 기대와 미측정 경계를 연결한다. 기존 RDF 1.1 projection,
SHACL 1.0, SPARQL 1.1, PROV-O 구현을 사용한다. 기존 최적화 원칙과 작업 중인 다른
작성자의 그래프를 덮어쓰지 않는다.

```sh
src/hswm/effect-runtime/bin/hswm-workspace show optimization-contract
src/hswm/effect-runtime/bin/hswm-workspace query optimization-contract rules
src/hswm/effect-runtime/bin/hswm-workspace query optimization-contract contracts
src/hswm/effect-runtime/bin/hswm-workspace query optimization-contract bottlenecks
src/hswm/effect-runtime/bin/hswm-workspace query optimization-contract boundaries
src/hswm/effect-runtime/bin/hswm-workspace query optimization-contract proofs
src/hswm/effect-runtime/bin/hswm-workspace validate optimization-contract
src/hswm/effect-runtime/bin/hswm-workspace bindings optimization-contract
```

[보강 그래프](../../ontology/identity/hswm_core/HSWM_OPTIMIZATION_CONTRACT_ONTOLOGY.v1.json),
[질의·관계 계약](../../ontology/queries/hswm_optimization_contract_2026-10-07/README.md),
[검증 기록](artifacts/hswm_optimization_contract_2026-10-07/validation.v1.json)을 연결한다.
`Context evaluation`은 graph·instructions 작업에, `CLI evaluation`은 cli·instructions
작업에만 추가로 선택된다. 상세 `Comparison contract`는 최적화 비교를 수행할 때 읽는다.

기존 여섯 원칙의 snapshot은 `3ee1983`의 출처 바이트를 보존한다. 이번에 살아 있는
`routes.json`에 선택 경로가 추가되므로, 옛 view의 worktree binding 검사에는 그 파일의
차이가 표시될 수 있다. 과거 hash를 갱신해 이 차이를 숨기지 않는다. 현재 선택 경로는
[보강 라우팅 관측](artifacts/hswm_optimization_contract_2026-10-07/routing-observation.v1.json)에서
확인하며, 이전 증거와 현재 적용 상태를 구분한다.
