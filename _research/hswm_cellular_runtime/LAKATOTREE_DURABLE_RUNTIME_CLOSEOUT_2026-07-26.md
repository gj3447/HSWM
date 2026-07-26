# LakatoTree durable-runtime closeout

상태: **ENGINEERING PASS / LAKATOTREE PARTIAL / SCIENCE UNJUDGED**

잠긴 v2 judge의 로컬 결과는 `9/9`, metric `1.0`이지만 라카토트리 verdict는 `partial@L0(client_asserted,replay_refuted)`이다. 이유는 두 층으로 분리됐다.

1. v2 judge는 JSON의 `"value": 1.0`을 출력하지만 producer-replay parser는 `metric=1.0` 계약을 요구했다.
2. 이를 수정하지 않고 위임하는 v3 adapter를 만들었으나, HSWM repo의 절대경로는 LakatoTree FF4 실행 허용 루트 밖이라 서버 재실행이 거부됐다.

두 partial receipt는 덮어쓰지 않았다. byte-identical judge를 기존 OS-temp 허용영역에 배치하는 v4 노드를 열었을 때 negative heuristic가 “5-node budget 소진, prediction hit 0, 연속 non-progressive 2”로 `ABANDON`을 발화했다. 설정을 약화하거나 추가 노드로 verdict를 세탁하지 않고 그 가지를 중단했다.

- 공학 구현: 로컬 Lean/Python/실제 Qwen 검증 PASS.
- durable-cell foundation: 9개 acceptance gate 근거로 `satisfied`.
- LakatoTree measurement sovereignty: PARTIAL, server-regenerated 아님.
- 과학적 HSWM 성과: 없음, `UNJUDGED`.
- 남은 required foundation: 6개.
- 다음 positive heuristic: `semantic-weight-metric-contract → operator-weight causal mediation`.
