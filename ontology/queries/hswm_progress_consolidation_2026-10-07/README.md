# HSWM 통합 진행 조회

[구성과 계약](../../../docs/research/HSWM_PROGRESS_CONSOLIDATION_2026-10-07.md)을 기준으로,
기존 plan/replay/adapter와 새 selection bundle을 동시에 읽는다.
검토 revision은 `b29cb8268b6f9e110739e40989f5bdf7ba8d3739`이고 live canonical 상태가 아니다.

| 질문 | alias / 파일 | 고정 검토 기준의 기대값 |
| --- | --- | --- |
| 지금 선택한 작업 관측과 완료 기준은? | [current](current.rq) | T1~T9 각각 하나, 모두 `OPEN`, 원래 의존 관계와 완료 기준 유지 |
| T1은 어떻게 진행됐나? | [history](history.rq) | 순서 0/1/2의 plan·replay·adapter 관측 3개 |
| 어느 출처가 어느 revision에 맞나? | [bindings](bindings.rq) | 출처 발생 39개: 검토 revision 일치 35, 역사적 차이 4 |
| 선택한 T1의 직접 근거는? | [evidence](evidence.rq) | 역할별 출처 13개, T2의 열람 자료 4개는 제외 |
| 다음에 어떤 한정 작업이 가능한가? | [next](next.rq) | T1·T2; 누락되거나 미완료인 선행 조건은 차단 |
| 증명·효능의 한계를 유지했나? | [boundaries](boundaries.rq) | PS-1~6 원래 판정, PS-3·5·6 미확립과 실제 부정 결과 유지 |

```sh
src/hswm/effect-runtime/bin/hswm-workspace validate progress
src/hswm/effect-runtime/bin/hswm-workspace query progress current
```

`current` 대신 위 alias를 사용할 수 있다. 응답의 `selectedSources`는 실제 읽은 primary와
고정된 추가 source의 해시를 보여 준다. source hash 불일치나 이중 node 소유는 거절된다.
query는 자동 실행이나 SHACL 검사 자체가 아니므로 구조 확인에는 `validate`를 사용한다.
기존 CLI는 결과를 canonical JSON 순서로 정렬한다. 작업·이력의 표시 순서는 응답의
`task`·`order` 값으로 읽으며 배열 위치를 진행 순서로 해석하지 않는다.

[shapes.ttl](shapes.ttl)은 선택 cardinality, typed role, provenance 필드, 미완료·비효능
경계를 검사한다. 별도 회귀 검사는 selector pointer/edge의 일치, 관측 이력, task DAG,
실제 답과 역사적 Git 바이트를 확인한다. count만 일치하는 답은 통과하지 않는다.
`history`는 이 v1 snapshot에 고정된 세 관측만 반환하며 선택 관측에서 정확히 두 predecessor
hop을 검증한다. 다른 T1 관측이나 일반 `REFERENCES` 경로로 범위를 넓히지 않는다.
