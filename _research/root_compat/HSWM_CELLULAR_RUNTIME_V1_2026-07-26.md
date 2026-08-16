# HSWM Cellular Runtime v1 — 엄밀 정의와 첫 개발 절편

상태: **ENGINEERING VERIFIED / SCIENCE UNJUDGED**

날짜: 2026-07-26

사용자 정전의 출발점: “작은 LLM 하나가 cell 같은 존재이고, 더 큰 LLM 하이퍼그래프에서 신경망 함수 하나처럼 동작한다.”

## 1. 무엇을 정의했는가

기존 [`formal/HSWMCellular.lean`](formal/HSWMCellular.lean)은 다음 정적 구조를 정의한다.

- `Cell`: 입력·출력 packet predicate와 total `step`을 가진 typed 함수 unit.
- `SemanticSynapse`: packet 묶음과 context를 다른 packet 묶음으로 보내는 의미 연결 연산자.
- `CellularHSWM`: cell 집합, typed synapse, 외부 입력·출력, 비어 있지 않은 cell topology.
- `Realization.asCell`: HSWM 전체가 다시 상위 HSWM의 cell로 들어갈 수 있다는 self-similar closure.
- `PlasticityClock`, `MorphogenesisClock`: weight update와 topology mutation의 상태 전이 자리.
- `LargerAIConditions`: 연결만으로 충분하지 않고 memory·joint credit·transfer·adaptation·retention이 모두 추가로 필요하다는 조건.

이번 [`formal/HSWMRuntime.lean`](formal/HSWMRuntime.lean)은 여기에 실행 가능한 최소 동역학을 더한다.

## 2. 수학적 narrow waist

한 cell 계약을

\[
c=(id_c,\tau_c^{in},\tau_c^{out})
\]

로 두고, 경계를 통과하는 packet을

\[
p=(id_p,\tau_p,x_p,H(x_p),H(\pi_p))
\]

로 둔다. 여기서 `τ`는 semantic packet type, `x`는 payload, `π`는 provenance다.

런타임 상태는

\[
s=(v,b,Q,Z)
\]

이다.

- `v ∈ ℕ`: 마지막 event version.
- `b ∈ ℕ`: 남은 activation budget.
- `Q`: pending activation의 유한 목록.
- `Z`: completed activation의 유한 목록.

커널은 세 순수 함수로 분리된다.

\[
D_\Gamma:S\times Command\to Rejection+Event^*
\]

\[
E:S\times Event\to S
\]

\[
\Phi:Event\to Effect^*
\]

`Γ`는 주입된 cell contract registry다. `D`는 command를 승인하거나 typed reason으로 거절하고, `E`는 승인·commit된 event만 replay하며, `Φ`만 외부 adapter가 수행할 일을 기술한다. LLM 호출은 `D`와 `E`의 공역에 존재하지 않는다.

## 3. v1 protocol

| 종류 | v1 원소 | 의미 |
|---|---|---|
| Command | `RequestCellStep` | typed input으로 cell activation 요청 |
| Command | `RecordCellOutput` | adapter가 반환한 typed output 기록 요청 |
| Event | `CellStepRequested` | budget을 1 소비하고 pending activation 생성 |
| Event | `CellStepCompleted` | pending을 완료로 이동 |
| Effect | `InvokeCell` | commit 뒤 adapter가 실행할 cell invocation |

거절은 `staleVersion`, `budgetExhausted`, `duplicateActivation`, `unknownCell`, `inputTypeMismatch`, `unknownActivation`, `outputTypeMismatch`로 닫혀 있다.

## 4. 증명·검증한 불변식

Lean4가 현재 증명하는 것은 다음이다.

1. version이 낡은 request는 `staleVersion`이다.
2. budget 0의 request는 `budgetExhausted`다.
3. 이미 존재하는 activation id는 중복 거절된다.
4. contract와 type이 맞는 request는 정확히 하나의 request event를 만든다.
5. pending이 없는 completion은 거절된다.
6. completion의 낡은 version과 잘못된 output type은 각각 명시적으로 거절된다.
7. pending과 output type이 맞는 completion은 정확히 하나의 completion event를 만든다.
8. request event는 budget을 정확히 1 소비한다.
9. completion event는 budget을 바꾸지 않는다.
10. request event만 정확히 하나의 `InvokeCell` effect를 만든다.
11. completion event는 effect를 만들지 않는다.
12. event history replay는 list 결합에 대해 합성된다.

Python 구현은 같은 protocol을 실제 immutable state로 실행하며, 추가로 다음을 검증한다.

- 같은 initial state와 history의 replay state 및 digest가 동일하다.
- out-of-order event와 admission을 우회한 completion은 실패한다.
- 거절 경로에서는 injected `CellPort`가 호출되지 않는다.
- adapter output도 반드시 `RecordCellOutput → decide → event → evolve` 경로로 돌아온다.

## 5. 어디까지 개발됐는가

이번 절편으로 “LLM 함수망 runtime 미구현”을 곧바로 **완료**로 바꾸지는 않는다. 정확한 상태는 다음이다.

- **완료**: typed cell activation의 순수 decision/replay/effect kernel.
- **완료**: Lean4 정의와 핵심 불변식 증명.
- **완료**: injected stub `CellPort`를 통한 첫 end-to-end vertical slice.
- **미구현**: 작은 LLM을 실제 호출하는 production adapter.
- **미구현**: atomic event store와 transactional outbox.
- **미구현**: 결과→credit→ΔW 폐루프.
- **미구현/미증명**: agent transfer, learned topology rewiring, consolidation/sleep.
- **미판정**: 위 요소들이 결합되어 “더 큰 범위의 AI”가 된다는 과학 주장.

즉, 이번 성과는 **연구 주장의 성립**이 아니라 그 주장을 거짓·참으로 판별할 수 있게 만드는 실행 기반의 첫 수직 절편이다.

## 6. 다음 구현 순서

1. `EventStore` + transactional outbox를 붙여 crash/retry에서도 model invocation이 중복되지 않게 한다.
2. 한 개의 작은 LLM adapter를 `CellPort` 뒤에 붙이고 deterministic fixture와 bounded live smoke를 분리한다.
3. output packet을 기존 `PlasticityClock.sealTrace`에 연결하되, credit과 `ΔW` 적용은 사전등록된 실험에서만 연다.
4. `semantic-weight-metric-contract` foundation을 먼저 충족한 뒤 operator-weight causal mediation 실험으로 들어간다.

엔진 경계·failure model·promotion gate의 기계판독 정본은 [`_research/hswm_cellular_runtime/engine_spec.v1.json`](_research/hswm_cellular_runtime/engine_spec.v1.json)이다.
