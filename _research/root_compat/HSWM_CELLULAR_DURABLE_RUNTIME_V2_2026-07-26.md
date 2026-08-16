# HSWM Cellular Durable Runtime v2

상태: **ENGINEERING PASS / SCIENCE UNJUDGED**  
날짜: 2026-07-26

## 결론

HSWM의 “작은 LLM cell이 함수처럼 실행되는 경로”는 이제 메모리 안의 데모를 넘어, SQLite event store와 transactional outbox를 통해 재시작 가능한 최소 수직 절편이 됐다. 실제 `qwen3.6-27b` cell 한 번도 `CellStepRequested → InvokeCell → CellStepCompleted` 경로로 완료했다.

이 결과가 곧 HSWM의 더 큰 AI 가설을 증명한 것은 아니다. 이번 사전등록이 판정한 것은 crash safety와 외부 효과 불확실성을 포함한 **실험 기반시설의 공학적 성립**뿐이다.

## 구현된 경계

- `hswm_cellular_store.py`: `BEGIN IMMEDIATE`, WAL, `synchronous=FULL` SQLite event store.
- request event, command receipt, stream state, outbox intent의 원자적 commit.
- completion event와 outbox `SUCCEEDED`의 원자적 commit.
- 같은 command의 exact retry는 새 event를 만들지 않음.
- 같은 idempotency key의 다른 intent는 `CommandIntentConflict`로 거절.
- 외부 호출 결과가 불명확하면 `UNKNOWN_OUTCOME`; 자동 재시도 금지.
- `hswm_cellular_openai.py`: stdlib HTTP 기반 OpenAI-compatible `CellPort`, 응답 크기 제한, 비밀 비영속화, activation id를 idempotency header로 전달.
- `formal/HSWMDurableRuntime.lean`: outbox 상태 전이와 unknown-outcome suspension 법칙.

## 사전등록 결과

잠긴 judge SHA-256는 `0fdad97294d9bb3450a64306aab4b45d87e1e1aca97d948440da74d5f48f8bb0`다. 구현 전에 고정한 9개 fault gate가 모두 통과했다.

| 게이트 | 결과 |
|---|---|
| request event + outbox 원자성 | PASS |
| reopen 뒤 pending effect 복구 | PASS |
| 경쟁 claim 단일 승자 | PASS |
| unknown outcome 자동 재시도 금지 | PASS |
| completion + success 원자성 | PASS |
| exact retry 무증분 | PASS |
| same key / different intent 거절 | PASS |
| replay digest 안정성 | PASS |
| typed CellPort completion | PASS |

고정 metric `durable_runtime_fault_gate_fraction`은 `1.0`이다. 이는 protective-belt engineering metric이며 과학적 excess prediction은 아니다.

## 실제 모델 검증과 실패에서 얻은 것

첫 실제 호출은 Qwen thinking mode의 빈 final content 때문에 typed text 계약을 만족하지 못했다. 호출이 서버에서 실행됐을 가능성이 있으므로 런타임은 이를 `UNKNOWN_OUTCOME`으로 영속화했고, 재시도하지 않았다. 출력이 없음을 확인한 뒤 그 effect를 `FAILED_PERMANENT`로 명시 종료했다.

그 다음 `chat_template_kwargs.enable_thinking=false`를 계약에 넣고 새 SQLite DB와 새 activation으로 한 번만 재검증했다. 결과는 다음과 같다.

- model: `qwen3.6-27b`
- request event sequence: `1`
- completion event sequence: `2`
- final outbox status: `SUCCEEDED`
- stream version: `2`
- output payload SHA-256: `567080b9f259dff8274ec0045bc31ab95744d6709a4672f8836a352bb4761252`

## 아직 구현되지 않은 것

- host approval과 interruption을 SQLite 권한 상태로 승격하는 것.
- 오래 남은 `IN_FLIGHT` effect의 lease-expiry/reconciliation protocol.
- endpoint가 보증하는 durable idempotency receipt와 exactly-once 판정.
- forward schema migration.
- 결과→credit→ΔW, agent transfer, topology learning, consolidation/sleep.

다음 과학 절편은 이 runtime 위에서 `semantic-weight-metric-contract`를 고정하고, 동일 trace에 대해 **operator weight를 바꿨을 때 결과가 causal하게 변하는지**를 사전등록·ablation하는 것이다. 그 전까지 이 구현은 HSWM 가설의 증거 생산 장치이지 가설 성공 판정 자체가 아니다.
