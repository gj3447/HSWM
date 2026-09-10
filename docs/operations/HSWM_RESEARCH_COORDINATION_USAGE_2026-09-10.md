# 연구 작업의 알 수 없는 사용량 기록

2026-09-10 · `SECONDARY_AI / ENGINEERING_ADDENDUM`.

[연구 조정 CLI](HSWM_RESEARCH_COORDINATION_2026-09-09.md)를 실제 협업에 사용하면서
작업자 token telemetry를 얻을 수 없는 경우를 확인했다. `hswm-research-graph/v1`의
FINISH는 이제 `usedTokens: null`도 받는다. 기존 숫자 입력은 그대로 유효하다.

| 입력·상태 | usageStatus | overBudget |
| --- | --- | --- |
| 사용량을 보고한 종료 | REPORTED | 보고값으로 계산한 true/false |
| 사용량이 불명인 종료 | UNKNOWN | null |
| 아직 종료하지 않음 | null | false, 완료 사용량 평가가 아님 |

알 수 없는 비용을 0이나 예산 이내로 바꾸지 않는다. 숫자도 호출자 보고값이며 provider
증명은 아니다. 후속 작업에는 선행 작업의 actor·model·사용량 상태가 함께 전달된다.
RDF에는 UNKNOWN 상태를 기록하고 알 수 없는 usedTokens/overBudget literal을 생략한다.
USL property view에는 null을 유지한다. 실제 연구·비용 효능 주장은 별도 측정이 필요하다.

기존 snapshot·과거 문서·source pin은 보존한다. 새 nullable 입력을 읽으려면 이 변경이
포함된 runtime을 빌드해야 하며 이전 runtime은 그 입력을 거부한다.
