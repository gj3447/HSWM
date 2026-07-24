# HSWM ordered research harness and feedback — 2026-07-24

## 결론

[`hswm_next_research_harness.py`](hswm_next_research_harness.py)는 이제 HSWM의 다음 실험을
병렬 아이디어 목록이 아니라 **한 번에 한 gate만 열리는 fail-closed 순서**로 관리한다.

```text
보존 증거(P1v4/B2.1/B2.2 groundwork)
  -> F1 실제 token/call parity + typed > flat/vector + role ablation
  -> B2.2 real three-pack Gate-0 acceptance
  -> P1v5 outcome -> eligibility -> persistent Delta-W -> removal
  -> P2 Agent-A weight packet -> byte-frozen Agent-B unseen transfer
  -> P3 one typed topology operation
  -> P4 homeostasis / sleep / scale
```

현재 active gate는 `F1_MULTI_LLM_FUNCTION_NETWORK` 하나다. 이 gate의 현재 의미는
actual-compute-matched F1이다. 실제 Qwen3.6-27B
R4는 3-call 구조와 removal/shuffle 방향은 보였지만, 네 항목 모두 consumed-token parity가
깨졌고 typed `2/4`가 vector `2/4`와 동률이었다. 따라서 하네스는 이를
`F1_DEVELOPMENT_REPAIR_REQUIRED`로 보존하고 뒤 gate를 열지 않는다.

## HSWM hard core와 하네스의 관계

이 순서는 HSWM을 일반 agent workflow로 축소하지 않는다. HSWM은 Hypergraph Semantic
Weight Map이며, typed macro-function node의 semantic activation/transition을 LLM이 실행하고,
외부 macro-synaptic `W`와 향후 `H`가 학습 대상이라는 hard core를 그대로 둔다.

각 gate가 닫는 인과 질문은 다음과 같다.

1. 여러 typed LLM 함수의 조성이 추가 호출량이 아니라 고유한 이득을 만드는가?
2. outcome이 실제 used bond의 persistent weight를 바꾸고, 그 delta를 제거하면 이득도
   사라지는가?
3. Agent A의 transcript나 parameter update 없이 그 weight 변화만으로 frozen Agent B가
   unseen 문제에서 좋아지는가?
4. weight-only transfer 이후 한 개의 typed hyperedge edit가 추가 인과 이득을 만드는가?

## 현재 상태 확인

```bash
.venv/bin/python hswm_next_research_harness.py status \
  --repo-root . \
  --recorded-at 2026-07-24T05:00:00+00:00
```

status receipt의 핵심 필드는 다음과 같다.

- `sequence_locked=true`: 계획이 한 active gate만 허용한다.
- `active_gate`: 지금 실행할 정확히 한 단계다.
- `ordered_remaining`: 아직 닫히지 않은 전체 순서다.
- `gates[].evidence`: 재검증된 receipt/judgment와 실패 원인이다.
- `scientific_prediction_registered=false` 및 `scientific_verdict_emitted=false`: 이
  orchestration harness 자체는 과학 판정을 만들지 않는다.

## Gate A — F1 actual-compute parity

새 F1은 judgment 문자열만 제출하지 않는다. 원본 suite와 독립 evaluator gold를 함께 주면
하네스가 기존 PROM-9 judge로 call receipt, prompt/registry binding, candidate universe,
actual input/output token, gold identity를 다시 검사한다.

```bash
.venv/bin/python hswm_next_research_harness.py status \
  --repo-root . \
  --f1-suite /absolute/write-once/f1-sealed-suite.json \
  --f1-gold /absolute/independent/f1-sealed-gold.json \
  --output /absolute/write-once/ordered-status-after-f1.json
```

F1은 다음 conjunction에서만 `SATISFIED`다.

```text
sealed mode
AND n >= 100 per arm
AND exact physical calls = 3 per item/arm
AND actual consumed-token spread <= preregistered tolerance
AND typed-flat paired bootstrap LCB > 0
AND typed > vector
AND role removal loses effect
AND role shuffle loses effect
```

sealed 결과가 conjunction을 깨면 `REJECTED`로 남고 보호대 수정 없이는 다음 gate가 열리지
않는다. development 결과는 수치가 좋아도 `ACTION_REQUIRED`다.

## Gate B0 — real Gate-0 component packs

F1이 닫힌 뒤 reproduction/full-2Wiki/full-MuSiQue pack을 만들고 기존 B2.2 validator가 lock,
pack hash, neutral replay, frozen-B2 replay, learner view를 다시 연다.

```bash
.venv/bin/python hswm_next_research_harness.py status \
  --repo-root . \
  --f1-suite /absolute/write-once/f1-sealed-suite.json \
  --f1-gold /absolute/independent/f1-sealed-gold.json \
  --gate0-acceptance /absolute/write-once/gate0-acceptance.json \
  --output /absolute/write-once/ordered-status-after-gate0.json
```

앞 gate가 닫히기 전에 `--gate0-acceptance`를 넣으면 하네스는 out-of-order evidence로
거부한다.

## Gate B — P1v5 real Semantic Weight Map plasticity

`--p1v5-packet`에는 결과 표가 아니라 base/candidate/promoted/removal snapshot, 실제
used-edge eligibility, independent evaluator, leakage audit, equal-budget audit와 열 개 arm의
row를 넣는다. 하네스는 [`prom_search_hswm/prom9_causal_harness.py`](prom_search_hswm/prom9_causal_harness.py)의
judge를 직접 다시 실행한다.

```bash
.venv/bin/python hswm_next_research_harness.py status \
  --repo-root . \
  --f1-suite /absolute/write-once/f1-sealed-suite.json \
  --f1-gold /absolute/independent/f1-sealed-gold.json \
  --gate0-acceptance /absolute/write-once/gate0-acceptance.json \
  --p1v5-packet /absolute/write-once/p1v5-causal-packet.json \
  --output /absolute/write-once/ordered-status-after-p1v5.json
```

`P1V5_SUPPORTED_NARROW`는 promoted snapshot이 실제로 달라지고, fresh gain/retention/canary를
통과하며, random credit/shuffled eligibility/static/no-promotion이 설명하지 못하고, exact
removal이 base `W`를 복원하면서 gain을 지울 때만 열린다. fast-only는 persistent Delta-W가
아니다.

## Gate C — P2 weight-only A-to-B transfer

`--p2-packet`도 하네스가 raw packet에서 재판정한다. Agent B의 model parameters, prompt,
tools, readout, budget manifest가 전후 byte-equivalent여야 하고 A transcript visibility,
exact-query cache hit, train/test component overlap이 모두 0이어야 한다.

```bash
.venv/bin/python hswm_next_research_harness.py status \
  --repo-root . \
  --f1-suite /absolute/write-once/f1-sealed-suite.json \
  --f1-gold /absolute/independent/f1-sealed-gold.json \
  --gate0-acceptance /absolute/write-once/gate0-acceptance.json \
  --p1v5-packet /absolute/write-once/p1v5-causal-packet.json \
  --p2-packet /absolute/write-once/p2-transfer-packet.json \
  --output /absolute/write-once/ordered-status-after-p2.json
```

그때만 P3의 단일 `CONNECT` topology experiment가 `READY`가 된다. 여러 topology operation,
weight rule, router를 한꺼번에 탐색하는 것은 허용하지 않는다.

## LakatoTree packet

검증한 status를 DRAFT engineering node용 packet으로 바꿀 수 있다.

```bash
.venv/bin/python hswm_next_research_harness.py lakatotree-packet \
  --repo-root . \
  --status /absolute/write-once/ordered-status.json \
  --result-path /opt/lakatotree/.runtime/research-current/HSWM/receipts/ordered-status.json \
  --output /absolute/write-once/ordered-lakatotree-packet.json
```

packet에는 prediction 등록이나 scientific result submit 명령이 없고, DRAFT node와 evidence
event만 있다.

## 연구 피드백

- 지금 접을 단계는 아니다. typed role removal이 `2/4 -> 0/4`로 떨어진 것은 약한 인과
  신호지만, vector 동률과 token mismatch 때문에 고유 이득은 아직 없다.
- 다음 실험은 prompt 수를 늘리는 일이 아니라 actual-token parity를 구조적으로 맞추는
  일이다. 입력을 arm별로 사후 truncate하지 말고 동일 token envelope/candidate bytes를
  사전 생성해야 한다.
- HSWM의 고유 결과는 `Delta-W`와 frozen-B transfer에서 갈린다. 이 둘이 없으면 현재 구현은
  강한 typed orchestration/memory system이지 아직 학습하는 semantic neural substrate는
  아니다.
- 두 번의 독립 fair F1에서도 typed가 vector와 동률이면 현재 3-function protective belt의
  고유 성능 주장을 중단하고 역할 분해나 state representation을 교체한다. hard core를
  자동 폐기하지는 않는다.
