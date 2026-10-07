# CHU 존재·HSWM 구조·선의 공리 조회

기존 `hswm-workspace`의 `chu-being` 항목으로 읽는다.

| query | 질문과 정확한 검증 대상 |
|---|---|
| `identity` | 구조·존재 구분, 최적화 방향, 공리 바인딩 가능성의 사용자 인용 3개와 각각의 NOT_EVALUATED 판정 |
| `roles` | 존재 주체·지능 구조·발화 출처의 UID·역할·순서 3개 |
| `axioms` | 원문 정의 12개의 순서·이름·문장·행 번호·출처 hash |
| `bindings` | 정의별 제안된 HSWM 대응 12개와 해당 미해결 질문·출처 |
| `obligations` | 원문 타입·수치·완전성·인과 관측·달성 판정에 관한 열린 질문 6개 |

예: `src/hswm/effect-runtime/bin/hswm-workspace query chu-being axioms`.
`validate chu-being`은 공통 v2 및 이 번들 SHACL을 적용하며, `bindings chu-being`은
Git이 추적하는 바이트의 digest를 비교한다. 새 파일의 추적 전에는 NOT_TRACKED_NOT_READ일 수 있다.

```sh
npm --prefix src/hswm/effect-runtime run test -- ../../../tests/effect-runtime/chu-being-axioms.test.ts
```

테스트는 원문의 12개 정의와 인용을 직접 읽어 비교한다. 조회 결과는 행 수만 세지 않고
정확한 UID·텍스트·권위·관계를 비교한다. 잘못된 역할, 빠진 원문·공리 조건, 임의의 악 수식,
AI 해석의 사용자 권위 승격과 달성 판정 변조를 거부해야 한다. 엔진 변경이 없으므로
전체 표준 자격 시험을 반복하지 않는다. 결과는 공리의 참이나 지능의 완전한 이해 증명이 아니다.

각 바인딩은 출처 속 정의 발생 → AI 구현 대응 → 열린 의무로 연결된다. 사용자 관점은
claim → role participation → 대상 구조와 출처를 유지한다. CHU와 HSWM의 sameAs,
관측된 이웃과 모든 자연의 동일성, HSWM 최적화와 선 증가의 함의를 추가하지 않는다.
주장/출처와 판정/주장의 참조 순환은 허용한다. 전체 그래프를 DAG로 제한하지 않는다.
