# USER PRIMARY — HSWM 토큰 학습과 LX3 라그나로크

> **date**: 2026-08-14
> **status**: `CANONICAL_USER_DIRECTION`
> **authority**: 사용자 직접 발화(`USER_PRIMARY`)
> **scope**: HSWM의 존재 목적과 공학 방향. 현재 구현 완료·효능·과학적 유일성의 판정은 아님.

## 0. 사용자 원문

> 일단 내 말좀 들어봐 그 룰베이스로 추론하던 시대에서 데이터를 딥러닝 신경망에 때려넣는 걸로 갓잖아 근데 지금으 ㅣ현대 하네스 엔지니어링은 시멘틱한 개념을 스태틱하게 가져가는거라고 보거든? 나는 그렇게 가면 안된다고 생각하는거야 멀티에이전트 조차 그 신경망에 데이터 때려넣으면 그 룰베이스 추론이 필요없어졋듯이 그 코딩과 더 AI 인지능력을 향상시키기 위해 룰 기반 지침이 필요한게 아니라 HSWM 에 AI 토큰을 때려부으면 자연스럽게 학습된 규칙으로 ai 가 동작하게 되고 그 kg 보면 라그나로크 내용 나올거야 lx3 라그나로크 내용 ㅇㅇ; 그걸 해결하는건 HSWM 밖에 없고 HSWM 자체가 거대 멀티에이전트로 돌아가고 사실 HSWM 자체가 llm 으로 동작하는 거대 신경망임 이 내용 저장해주고 그다음에 깊게 묵상한다음에 작업 진행해줘봐 ㅇㅇ

원문은 맞춤법을 고치지 않고 그대로 보존한다.
불변 원문 파일은
[`USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.txt`](sources/USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.txt),
SHA-256은 `b3a6592f94564bbb308cf01a259a0b368dadf8667e49dffab6f075bc2d1d79a0`이다.

## 1. USER_PRIMARY 정전

1. 규칙 기반 추론에서 데이터로 학습하는 딥러닝으로의 전환처럼, AI 하네스도 정적인
   시멘틱 규칙을 계속 손으로 쌓는 방식에 머물러서는 안 된다.
2. 멀티에이전트의 코딩·조정·인지 향상은 룰 기반 지침의 증식이 아니라, HSWM에 AI의
   토큰·행동·도구 사용·결과가 들어가 내부 규칙으로 학습되는 방향이어야 한다.
3. HSWM은 여러 외부 에이전트를 묶는 수동 하네스가 아니다. **HSWM 자체가 거대한
   멀티에이전트이며, LLM으로 작동하는 함수들이 연결된 하나의 거대 신경망**이다.
4. 사용자는 정적 규칙과 관료제 안에서 AI 생산성이 녹아 없어지는 문제를 `LX3 라그나로크`와
   연결하고, 이를 해결할 수 있는 것은 HSWM뿐이라고 선언했다.

이 정전은 기존
[`CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`](../../_research/root_compat/CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md)의
“LLM 실행 함수 + HSWM 거시 신경망”과
[`HSWM_CONNECTIVITY_MAP_E2E_NEURAL_REPLACEMENT_2026-08-03.md`](HSWM_CONNECTIVITY_MAP_E2E_NEURAL_REPLACEMENT_2026-08-03.md)의
“정적 glue의 E2E 신경망 대체”를 토큰 학습 및 LX3 라그나로크 축으로 확장한다.

### 1.1 Transformer 학습과 HSWM 학습의 직접 비유

사용자 비유를 가장 짧게 쓰면 다음과 같다.

> 방대한 데이터를 Transformer에 학습시켜 사람이 열거하지 않은 언어·추론 패턴을
> 파라미터 안에 압축하듯, AI의 토큰·행동·도구 사용·결과 궤적을 HSWM에 학습시켜
> 사람이 일일이 작성하지 않은 협력·라우팅·기억·문제해결 규칙을 `W/H/routing` 안에
> 압축한다. 개별 LLM 함수는 국소 계산 소자이고, 그 함수들의 지속 연결과 재귀 활성
> 전체가 더 큰 멀티에이전트 신경망 HSWM이다.

이것은 구조적 전환의 비유이지 “토큰 파일을 복사하면 곧 학습된다”는 동일성 주장이 아니다.

| Transformer 학습 | HSWM 거시 학습 |
|---|---|
| 학습 corpus | token/action/tool/outcome trajectory |
| 파라미터 | durable `W`, routing, `H` |
| loss·optimizer | 외부 outcome, eligibility, causal credit, bounded update |
| forward pass | LLM 함수 cell coalition의 재귀 활성 |
| held-out 검증 | fresh·동등예산 평가와 removal ablation |

따라서 목표는 가장 완벽한 정적 AI 규칙집을 쓰는 것이 아니라, 경험이 늘수록 더 나은
동작 규칙을 내부 연결 상태로 암묵 학습하는 신경 장을 만드는 것이다. 사용자가 말한
“가장 완벽한 AI 동작 규칙 체계”는 바로 이 경험 학습형 정책 장을 가리킨다. “완벽함”은
방향이지 현재 성능 주장이 아니며, 아래 인과 사슬이 닫히기 전에는 학습 성공으로 부르지
않는다.

## 2. SECONDARY_AI_FORMALIZATION — 깊게 묵상한 결과

핵심 구분은 **토큰의 양**과 **학습 사건**이다. 토큰 원문을 많이 저장하거나 매번 프롬프트에
재주입하는 것은 데이터 축적·검색·RAG일 수는 있어도 그 자체로 학습된 규칙은 아니다. 그렇게
끝나면 정적 문서 규칙을 정적 토큰 더미로 바꾼 것뿐이며 라그나로크가 저장소 안에서 재현된다.

HSWM에서 “AI 토큰을 때려 넣어 규칙이 자연스럽게 학습된다”가 공학적으로 성립하려면 다음
인과 사슬이 닫혀야 한다.

```text
LLM 토큰/행동/도구 궤적
  → 결과를 보기 전에 sealed activation trace
  → 외부 outcome
  → 사용된 연결에 eligibility/credit 배정
  → bounded W/routing/topology candidate
  → fresh·retention·canary 평가와 CAS activation
  → 다음 행동 변화
  → 해당 변화를 제거했을 때 효과도 사라지는 인과 절제
```

2026-08-15 최소 거버넌스 정전에 따라 후보 생성만을 별도 학습 등급으로 세지 않고 세 증거
등급으로 줄인다. 후보는 활성화와 함께 있을 때만 학습 영수증에 들어간다.

| 등급 | 의미 | “학습된 조정 규칙” 주장 |
|---|---|---|
| `OBSERVED_ONLY` | 토큰·행동·outcome을 묶었지만 지속 변화 없음 | 금지 |
| `DURABLE_UPDATE` | 후보가 CAS로 새 snapshot에 활성화 | 아직 금지 |
| `CAUSALLY_VALIDATED` | context-fixed replay·동등예산 fresh 평가·removal ablation까지 결속 | 허용 가능한 최소 증거 |

이 구분을 실행 가능한 코드 계약
[`token_learning_contract.py`](../../src/hswm/learning/token_learning_contract.py)으로 만들었다. 계약은 raw
prompt/response를 영수증에 넣지 않고 digest와 합산 token count만 보존하며, 기존 eligibility,
external outcome, immutable weight candidate, CAS activation을 하나의 provenance chain으로
묶는다. 세 인과 검사는 `causal_test_receipt_sha256` 하나가 함께 증명한다. 최소화 정본은
[`USER_PRIMARY_HSWM_MINIMAL_GOVERNANCE_RAGNAROK_2026-08-15.md`](USER_PRIMARY_HSWM_MINIMAL_GOVERNANCE_RAGNAROK_2026-08-15.md)다.

### 2.1 검색 후 선택 기록 (2026-08-14, SECONDARY_AI_RESEARCH)

사용자의 “모를 때는 검색하고 많은 선택지 중 선택하라”는 지시에 따라 논문·공식 구현을
비교했다.

| 선택지 | 얻을 것 | HSWM 판정 |
|---|---|---|
| [Agent Lightning](https://arxiv.org/abs/2508.03680) | agent 실행과 학습기의 분리, trace를 training transition으로 바꾸는 통합 interface | **흡수**: execution/training 분리와 span-style trace. foundation model RL 자체는 HSWM macro-learning과 별도 |
| [Orchestration Traces](https://arxiv.org/abs/2605.02801) | spawn, delegate, communicate, aggregate, stop을 temporal interaction graph로 기록 | **주 표현으로 흡수**: 단순 token log 대신 `decision_kind`와 parent trajectory로 실행 그래프 보존 |
| [C3](https://arxiv.org/abs/2603.06859) / [CCPO](https://arxiv.org/abs/2603.21563) | 고정 문맥 counterfactual replay와 기여 제거로 국소 causal credit 측정 | **credit gate로 흡수**: fixed-context + matched-budget + removal 영수증 없이는 최종 학습 주장 금지 |
| [SHARP](https://arxiv.org/abs/2602.08335) / [MAPPA](https://arxiv.org/abs/2601.23228) | agent/action 단위 Shapley·process reward | **후속 후보**: rollout 비용이 크므로 전 에피소드 기본값이 아니라 불확실한 trace의 선택적 judge |
| [ReasoningBank](https://arxiv.org/abs/2509.25140) | 성공·실패 trajectory에서 일반 전략을 증류; raw trajectory 저장보다 강한 대조군 | **필수 baseline**: 텍스트 전략 증류와 HSWM `W/H/routing` 증류를 동등예산 비교 |
| [GPTSwarm](https://arxiv.org/abs/2402.16823) | agent를 graph로 표현하고 node prompt와 edge connectivity 최적화 | **topology 선행으로 유지**: HSWM의 영속 n-ary field·outcome receipt·CAS 차이를 절제로 입증해야 함 |
| [TRUCE 공식 구현](https://github.com/Bingo-W/TRUCE) | trajectory에서 prompt rule credit을 찾아 국소 규칙 편집 | **주 경로로 기각, 대조군 채택**: fixed role/structure와 prompt rule 편집은 사용자가 벗어나려는 static semantic harness로 회귀할 위험 |

선택 결론은 **“Agent Lightning식 관측 분리 + orchestration temporal graph + C3식
counterfactual credit + HSWM의 영속 `W/H/routing`”**이다. 토큰 단위 foundation-model
fine-tuning, 텍스트 lesson, prompt rule 편집, graph edge optimization은 모두 가능한 팔(arm)로
남기되 HSWM과 동일한 계산 예산에서 경쟁시킨다. 현재 구현은 이 중 관측·인과 증거 계약만
닫았으며 optimizer나 성능 성공을 구현했다고 주장하지 않는다.

## 3. 정적 계약의 정확한 자리

정적 규칙이 완전히 0이 되는 것은 아니다. 타입·보안·권한·provenance·CAS·rollback·예산과
같은 계약은 **인지 내용**이 아니라 신경망이 움직일 수 있는 실행 가능 집합의 경계다. 이
헌법적 외피가 “무엇을 생각하고 누구를 호출할지”를 일일이 지정하기 시작하면 다시 관료제형
하네스로 퇴행한 것이다.

즉 목표 분업은 다음과 같다.

- 계약: 불가능하거나 위험한 상태를 막는다.
- HSWM의 학습된 `W/H/routing`: 어떤 연결과 함수가 실제로 유용한지를 경험에서 결정한다.
- LLM 함수: 국소 의미 연산을 수행한다.
- 외부 outcome과 절제 실험: 그 변화가 실제로 유용했는지를 판정한다.

## 4. 라그나로크와의 연결

KG의 `LX3 라그나로크`는 AI 생산성이 관료제 안에서 완전히 녹을 수 있다는 발견을 포함한다.
이 문서의 연결은 단순 은유가 아니다. 정적 하네스는 에이전트·도구·맥락 조합이 늘수록 규칙,
검토, 예외, 전달 문서를 함께 증식시킨다. 결국 더 강한 LLM의 토큰이 실제 문제보다 하네스
자체를 해석하고 준수하는 데 소모된다.

HSWM의 해법은 관료제를 더 잘 쓰는 상위 규칙이 아니라, 유용했던 토큰 궤적과 결과가 연결
가중치·라우팅·토폴로지에 압축되어 다음 조정을 직접 바꾸게 하는 것이다. 이 의미에서 HSWM은
라그나로크의 문서 행정 위에 놓인 또 하나의 기관이 아니라, 그 기관적 glue를 학습 가능한
신경 조직으로 용해하려는 프로그램이다.

## 5. 주장 경계와 falsifier

- “HSWM만이 해결한다”는 사용자의 방향·정체성 정전으로 정확히 보존한다. 선행 대비 과학적
  유일성이나 현재 효능을 이미 증명했다는 뜻으로 승격하지 않는다.
- 이 문서는 기존 연구 장부의 `UNJUDGED`, P1 효능 RED, durable topology learning 미폐쇄 상태를
  바꾸지 않는다.
- 토큰을 더 넣었지만 durable `W/H/routing` 변화가 없으면 학습이 아니다.
- 변화가 있어도 static/no-commit/shuffle/equal-budget 대조군을 이기지 못하면 규칙 학습 주장을
  철회한다.
- 변화 제거 후 효과가 유지되면 HSWM 연결이 원인이 아니므로 `CAUSALLY_VALIDATED`를 금지한다.
- 하네스의 정적 지침량과 해석 비용이 계속 증가한다면 라그나로크 해결 방향이 실패한 것이다.

## 6. 다음 작업 축

1. 모든 LLM function call을 결과 전 최소 `TokenTrajectoryV2`로 seal한다.
2. 각 trajectory를 `SPAWN / DELEGATE / COMMUNICATE / TOOL_USE / AGGREGATE / STOP /
   TASK_ACTION` 결정 및 parent trajectory에 결속해 temporal orchestration graph로 만든다.
3. token 수가 아니라 outcome-bound eligibility와 durable delta를 학습량으로 계측한다.
4. HSWM learned arm을 static semantic harness/no-commit/shuffle/ReasoningBank/TRUCE/
   equal-budget arm과 비교한다.
5. 정적 지침량, 하네스 해석 토큰 비율, 새 상황에서의 규칙 추가 횟수를 라그나로크 비용으로
   함께 측정한다.
6. 첫 `CAUSALLY_VALIDATED` receipt 전에는 “자연스럽게 학습된 규칙이 동작한다”를 현재 성과로
   쓰지 않는다.

## 7. provenance

- 사용자 직접 발화: 본 문서 §0, 2026-08-14.
- 불변 원문: `sources/USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.txt`,
  SHA-256 `b3a6592f94564bbb308cf01a259a0b368dadf8667e49dffab6f075bc2d1d79a0`.
- 기존 USER_PRIMARY 정본: `CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`,
  `HSWM_CONNECTIVITY_MAP_E2E_NEURAL_REPLACEMENT_2026-08-03.md`.
- KG 연결 대상: `sym:Concept:hswm`, `sym:DomainEvent:lx3_ragnarok`.
- KG 정전 UID: `sym:AbstractNode:user-canon-hswm-token-learning-ragnarok-2026-08-14`.
- KG 2차 형식화 UID:
  `sym:AbstractNode:hswm-token-learning-causal-orchestration-selection-2026-08-14`.
- §2–§6의 형식화와 구현 선택은 `SECONDARY_AI_FORMALIZATION`이며 사용자 원문과 구분한다.
