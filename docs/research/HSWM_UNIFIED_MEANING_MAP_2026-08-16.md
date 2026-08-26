# HSWM 통합 의미 지도

> **상태:** `HISTORICAL_SYNTHESIS / SUPERSEDED_NAVIGATION`
> **기준 시점:** 2026-08-20
> **과학적 상태:** `UNJUDGED`
> **권위 경계:** 이 문서는 흩어진 뜻을 한 좌표계에 놓는 파생 지도다. 사용자 원문을
> 새로 쓰거나, 기존 정전을 소급 변경하거나, 실험 결과를 승격하지 않는다.
> **2026-08-26 supersession notice:** 이 문서의 fixed `H/W/A/F/Π` 통합은 당시의
> `SECONDARY_AI` navigation formalization으로만 보존한다. 현행 정본은 fixed roles를
> 폐기하고 schema-approved canonical atom마다 exactly one responsibility owner를 둔다.
> 현재 진입점은
> [`single-owner canon`](../canon/USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.md)과
> [`scientific-philosophy research`](HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_SCIENTIFIC_PHILOSOPHY_2026-08-26.md)다.

HSWM은 문서마다 메모리 substrate, semantic field, LLM function network, cellular
metaneural system, plastic cognitive wiring, larger AI, world self-model로 불려 왔다.
이 표현들은 서로 다른 물건의 이름이 아니라 **같은 연구 대상을 서로 다른 높이와
완성도에서 본 말**이다. 혼란의 주원인은 목표와 현재 구현, scalar 측정치와 target
operator, 철학적 목적과 과학적 증거가 같은 문장 안에서 자주 만났다는 데 있다.

이 문서는 그 파편을 하나로 읽기 위한 2026-08-20 당시 진입점이다.

## 1. 가장 짧은 통합 정의

> **HSWM은 token을 활성과 경험의 운반체로 삼아 LLM이 국소 의미 함수세포로 실행되고,
> evolving n-ary hypergraph `H`, macro-semantic coupling `W`, run-local activation `A`가
> 재귀적으로 함께 움직이는 자기유사 거시 신경망이다. 이 동일한 상태가 living harness의
> 역할과 실행 가능한 world model의 역할을 하며, 외부 outcome에 결속된 continuous
> learning으로 `W`, routing, `H`를 바꾸어 경험이 다음 행동의 원인이 되게 한다.**

권한, 타입, 거래, provenance, 예산, rollback, 안전 제약은 학습되는 인지 내용이
아니라 얇은 결정론적 경계 `Π`로 남는다. 이 정의는 **목표 정체성**이다. 현재 저장소는
evidence-preserving substrate, 결정론적 field/runtime, 학습 영수증 계약과 좁은
실험들을 구현했지만, causally validated durable macro-learning을 아직 보여 주지 못했다.

따라서 HSWM을 정확히 말하려면 항상 두 문장을 함께 써야 한다.

1. **무엇이 되려는가:** LLM 함수들 사이의 지속적인 거시 연결과 학습을 소유하는 더 큰
   신경 시스템이다.
2. **지금 무엇인가:** 그 목표를 부분별로 구현하고 반증하는 연구 저장소이며, 완성된
   자기학습 인지체가 아니다.

## 2. 권위는 한 파일이 아니라 역할별 계층이다

| 역할 | 읽어야 할 출처 | 이 지도에서의 취급 |
|---|---|---|
| 사용자 원문과 방향 | [`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md)와 결속된 [`2026-08-20 원문`](../canon/sources/USER_PRIMARY_HSWM_LIVING_HARNESS_WORLD_MODEL_2026-08-20.txt), [`USER_PRIMARY_HUMAN_UNIVERSAL_BODY_DISTINCTION_2026-08-20.md`](../canon/USER_PRIMARY_HUMAN_UNIVERSAL_BODY_DISTINCTION_2026-08-20.md), [`USER_PRIMARY_HSWM_WORLD_SELF_MODEL_2026-07-29.txt`](../canon/sources/USER_PRIMARY_HSWM_WORLD_SELF_MODEL_2026-07-29.txt), [`USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md`](../canon/USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md), [`USER_PRIMARY_HSWM_MINIMAL_GOVERNANCE_RAGNAROK_2026-08-15.md`](../canon/USER_PRIMARY_HSWM_MINIMAL_GOVERNANCE_RAGNAROK_2026-08-15.md) | 최신 `USER_PRIMARY` 방향과 그 통합 헌법은 파생 설명보다 우선한다 |
| 상위 통합 정전 | [`THE_WORLD_REMEMBERS.md`](../canon/THE_WORLD_REMEMBERS.md) | 세계 자기기억, 인간·LLM의 위치, 두 번째 신경망화를 한 목적 아래 묶는다 |
| 기술 정체성 | [`CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`](../../_research/root_compat/CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md), [`HSWM_CANONICAL_RESEARCH_DIRECTION_20260724.md`](../../_research/root_compat/HSWM_CANONICAL_RESEARCH_DIRECTION_20260724.md) | hard core와 교체 가능한 설계를 구분한다 |
| 수학·세포 형식화 | [`HSWM_MATH_DEFINITION_UNIFIED_2026-07-26.md`](../canon/HSWM_MATH_DEFINITION_UNIFIED_2026-07-26.md), [`DEFINITION_HSWM_CELLULAR_METANEURAL_SYSTEM_2026-07-26.md`](../../_research/root_compat/DEFINITION_HSWM_CELLULAR_METANEURAL_SYSTEM_2026-07-26.md) | `SECONDARY_AI_FORMALIZATION`; 사용자 원문이나 실측을 대체하지 않는다 |
| 현재 공개 상태 | [`README.md`](../../README.md), [`INDEX.md`](../../INDEX.md), [`EFFICACY.md`](../../EFFICACY.md) | 구현·실험·실패·미완료 여부의 현재 진입점이다 |
| 실행 계약과 직접 증거 | `src/`, `tests/`, `research/`, `evidence/`, `receipts/`, `results/`, `prereg/` | 코드 PASS는 공학 closure이고, 효능은 결속된 측정 범위 안에서만 말한다 |
| 저장소 의미 지도 | [`ontology/`](../../ontology/) | 경로와 개념의 탐색 장치다. HSWM의 두뇌나 행동 규칙이 아니다 |
| 이 문서 | 현재 파일 | 위 계층을 연결하는 색인이다. 새 정전·새 실험 결과가 아니다 |

뒤 문서는 앞 문서를 대체했다기보다 범위를 확장하고 정밀화한 경우가 많다. 다만 현재
운영 authority는 최신 사용자 방향을 따른다. 예를 들어 과거 외부 판정·개인 거버넌스
절차는 2026-08-15 최소 거버넌스 방향 이후 현재 권위를 갖지 않는다.

## 3. 하나의 HSWM을 열 개의 의미 렌즈로 보기

| 렌즈 | HSWM이 뜻하는 것 | 흔한 범주 오류 |
|---|---|---|
| 이름 | **Hypergraph Semantic Weight Map** | 이름의 `Map`을 단순 key-value 저장소로 읽기 |
| 존재론 | 지속되는 관계·가중치·활성·함수의 한 결합 객체 | 코드 파일 하나나 LLM 하나를 HSWM 전체로 부르기 |
| 신경망 정체성 | LLM-executed function cell들을 잇는 macro-neural system | foundation model 내부 weight와 HSWM의 `W`를 동일시하기 |
| 수학 | `H`, `W`, `A`, `F`가 결합되고 `Π`가 경계를 강제하는 동역학 | 서로 다른 구현 투사를 경쟁 정의로 보기 |
| runtime | typed cell, durable store, recurrent activation, bounded side effect | runtime 재생 성공을 학습 효능으로 보기 |
| 학습 | outcome-bound credit이 durable `ΔW/routing/ΔH`를 만들고 행동을 바꾸는 과정 | token 저장, 검색, prompt 편집, fast activation을 학습이라 부르기 |
| 합성 | 원자와 합성체가 같은 타입인 open self-similar HSWM | 고정된 1층/2층 또는 중앙 commander를 필수 구조로 보기 |
| 공학 방향 | static agent/tool/Skill/MCP glue의 인지 배선을 가소화 | 권한·안전·transaction까지 확률적 학습에 넘기기 |
| 철학적 목적 | 차이를 지우지 않고 세계가 자신의 흔적과 관계를 이어 가는 명시적 인지기관 | 물리학 명제, 인간 복제, 단일 집단의식으로 읽기 |
| 연구프로그램 | 위 목표를 분해해 구현하고 kill condition으로 반증하는 실험 묶음 | 목표 문장을 현재 입증된 성능으로 읽기 |

2026-08-20 헌법은 이 렌즈 중 **신경망, living harness, world model, continuous
learner가 한 객체의 네 기능적 얼굴**임을 고정한다. harness의 가독 문서 표현은
`Readout(H,W,A,F,Π)`이지, HSWM 밖에서 명령하는 별도 static controller가 아니다.

이 열 렌즈는 다음 네 층으로 압축할 수 있다.

| 층 | 뜻 | 현재 지위 |
|---|---|---|
| `L0` substrate | 세계·증거를 stable identity, provenance, immutable cut, fail-closed readout으로 보존 | 가장 많이 구현·검증됨 |
| `L1` function network | LLM 의미 함수들이 `H/W/A`를 통해 재귀적으로 활성화되는 거시 신경망 | 목표 정체성; 일부 runtime과 메커니즘 구현 |
| `L2` open composition | 여러 HSWM이 같은 타입으로 connect/separate/specialize되는 자기유사 시스템 | 구조적 합성은 있으나 learned composition은 미폐쇄 |
| `L3` larger AI / world self-model | 인간·AI·문서·센서·사건의 흔적을 잇는 지속적인 세계 자기기억 | 사용자 방향과 상위 목적; 과학적으로 미입증 |

`L0`의 테스트 성공은 `L1–L3`의 성공을 자동으로 증명하지 않는다. 반대로 `L3`의 큰 목적은
`L0`의 작은 공학 결과를 무의미하게 만들지 않는다. HSWM 연구는 이 층들을 **계보는
연결하되 증거는 분리**하는 작업이다.

## 4. 통합 객체와 한 번의 동역학

가장 작은 공통 좌표는 다음과 같다.

```math
\mathrm{HSWM}_t = (H_t, W_t, A_t, F_t, \Pi_t)
```

| 기호 | 통합 의미 | 지속성 |
|---|---|---|
| `H` | typed vertex와 evidence-bearing n-ary relation의 mutable hypergraph topology. 무엇이 함께 상호작용할 수 있는지를 정한다 | topology snapshot으로 지속 가능 |
| `W` | 함수·상태·관계 사이의 macro-semantic coupling. 강도뿐 아니라 신뢰, 억제, transport, gate, uncertainty, eligibility를 포함하는 target synapse다 | query-local `j`는 휘발하지만 target `θ_fast/θ_slow`는 둘 다 outcome-learned efficacy다 |
| `A` | 지금 run에서 token을 운반체로 실제로 흐르는 node/relation/trajectory의 activation과 working state | 의도적으로 휘발 |
| `F={f_i}` | typed port, role, local state, position, read/write authority를 가진 의미 함수세포. LLM은 이 함수를 실행하는 semantic transition operator다 | cell identity와 state는 모델 checkpoint와 분리 가능 |
| `Π` | capability, type, authority, transaction, idempotency, provenance, budget, rollback, safety를 강제하는 deterministic control plane | 헌법적 경계로 지속 |

한 foundation model이 여러 logical cell을 실행할 수 있다. 따라서 cell 하나마다 별도 모델이
필요하지 않다. 반대로 같은 모델 checkpoint를 썼다고 두 cell이 같은 cell인 것도 아니다.
정체성은 역할, ports, state, graph position, authority에서 나온다.

이 tuple은 **현재 단일 runtime의 class diagram이 아니라 통합 target 좌표**다. 실제 코드에는
수치 retrieval용 `H`와 evidence/provenance 합성용 symbolic `H`가 목적에 따라 공존하고,
`W`는 주로 scalar projection이며, `A`는 query score·typed packet·개별 activation event로
나뉘어 있다. `H` 위를 순환하는 하나의 semantic activation field와 recurrent scheduler는
아직 없다.

여기서 신경망이라는 말은 end-to-end differentiable backprop을 필수 조건으로 삼지 않는다.
정전이 잡은 본질은 **weighted connection + activation + outcome-dependent plasticity**다.
cell이 black-box LLM이거나 선택이 discrete여도 이 세 조건과 인과 검증을 실제로 만족하면
macro-neural system이 될 수 있다. 반대로 LLM을 여러 번 호출하는 것만으로는 부족하다.

### 한 번의 전체 흐름

```text
세계의 문서·사건·센서·사람·AI 흔적
  → provenance가 보존된 world/evidence state와 certified cut
  → 입력이 run-local A를 점화
  → H가 가능한 n-ary 상호작용을 제한
  → W가 어떤 cell/관계가 얼마나 전달·억제·활성화될지 조절
  → LLM-executed F가 재귀적으로 의미 변환·도구 사용·행동을 수행
  → 독립적으로 측정된 outcome
  → 활성 trajectory의 eligibility와 causal credit
  → bounded ΔW / routing / ΔH candidate
  → fresh·retention·canary·equal-budget·removal 검증
  → CAS/atomic activation 또는 reject/rollback
  → 다음 run의 행동 변화
```

`Π`는 이 흐름 전체를 둘러싸되 어느 cell을 생각하게 할지, 어떤 협업 패턴이 유용한지를
고정 규칙으로 대신 결정하지 않는다. 반대로 학습기는 `Π`를 우회할 권한이 없다.

## 5. 파편화가 가장 심했던 `H`, `W`, `A`, cell의 정확한 관계

### `H`: 저장 그래프, 활성 가능성, 학습 topology

`H`는 단지 문서 연결 그래프가 아니다. target에서는 함수, 상태, evidence, tool, outcome이
n-ary relation으로 함께 결속될 수 있는 interaction topology다. 현재 코드의 hypergraph와
world graph는 이 의미의 일부 projection이다. 현재의 결정론적 `compose`나 저장 구조가
있다는 사실과, outcome으로 `CONNECT / SEPARATE / SPECIALIZE`를 학습했다는 주장은 다르다.
후자는 아직 미폐쇄다.

### `W`: 하나의 숫자에서 operator-valued synapse까지

문서에 보이는 여러 `W`는 다음 표현 사다리로 읽어야 한다.

1. **측정 가능한 scalar projection:** 예를 들어 activation, bond score, query potential을
   더하는 retrieval/readout score. 현재 실험과 코드가 가장 많이 다루는 층이다.
2. **현재 통합 제안의 두 층:** durable slow `(ℓ,b)`와 query/run-local fast potential `j`를
   분리한다. 여기서 `j`가 커졌다는 사실은 durable learning이 아니다.
3. **cellular target operator:** relation compatibility, message transport, gating,
   excitatory/inhibitory efficacy, uncertainty, provenance, eligibility와 함께
   outcome-learned `θ_fast/θ_slow`를 가진 조건부 연산자다. 여기서는 두 `θ`가 모두
   plastic synapse이고 보존 시간척도가 다르다.

따라서 scalar `W`는 틀린 옛 정의가 아니라 operator-valued `𝒲`의 좁은 측정 그림자다.
foundation model parameter는 cell 내부의 **micro-weight**, HSWM `W/H`는 cell 사이의
**macro-weight/connectivity**다.

여기서 **semantic**은 embedding 좌표 그 자체가 아니다. 특정 문맥에서 한 cell이 다른
cell의 이후 계산과 외부 outcome을 어떻게 바꾸는가라는 **conditional causal
disposition**이다. 그래서 provenance, truth/validity, query relevance, usage, freshness,
transfer evidence를 scalar 하나로 섞어서는 안 된다. 필요한 경우 scalar는 그중 명시된
한 projection으로만 읽는다.

### `A`: 현재 생각과 장기 기억을 분리하는 경계

`A`는 지금 활성화된 coalition과 working state다. query가 지나가며 activation이 변하고
route가 달라져도 그 자체는 학습이 아니다. 다음 run까지 살아남는 certified `W/H` 변화와
world snapshot이 장기 상태를 만든다. 이 구분이 없으면 context, cache, retrieval,
learning이 모두 같은 단어가 된다.

### `F`와 cell: agent보다 작고, 단순 함수보다 크다

`f_i`는 scalar ReLU가 아니라 자연어·구조 상태를 다른 의미 상태로 바꾸는 typed stochastic
function이다. 한 cell은 planner, verifier, retriever 같은 role 이름만으로 정의되지 않고
입출력 port, local state, 위치, 권한까지 포함한다. 기존 agent는 하나 이상의 cell이나
일시적 coalition으로 재해석할 수 있지만, free-form chat swarm 자체가 HSWM인 것은 아니다.

cellular 형식의 더 풍부한 tuple과 operator synapse는 이 작은 공통 좌표를 폐기하지 않고
cell state, uncertainty, eligibility, memory, gate, policy를 펼쳐 쓴다.

표기 자체도 합치면 안 되는 부분이 있다. 통합 수학의 `α(e,c)`는 query-relative fast
attention이고 `A_t`가 activation이다. cellular tuple의 소문자 `α_t`는 topology proposal/
gate state, 대문자 `A_t`는 semantic activation packet이다. 같은 그리스 문자를 썼다는
이유로 attention, topology gate, activation을 하나의 상태로 취급하지 않는다.

## 6. 세 개의 시계와 두 종류의 weight

HSWM의 시간은 하나가 아니다.

| 시계 | 일어나는 일 | 학습으로 세는가 |
|---|---|---|
| activation / inference | 입력에 따라 `A`와 fast potential이 움직이고 cell coalition이 실행됨 | 아니오 |
| plasticity | outcome과 eligibility로 operator `θ_fast/θ_slow`·routing 후보를 만들고 검증·활성화함 | causal 조건을 만족할 때만 |
| morphogenesis | relation 생성·분리·전문화, 즉 `H` topology 자체를 바꿈 | causal 조건을 만족할 때만 |

`fast`라는 말은 두 좌표계에서 다르게 쓰인다. query-fast `j`는 현재 run의 잠재라서
비학습이고, cellular `θ_fast`는 outcome으로 갱신되는 짧은 plastic state다. `θ_slow`는 더
긴 반복·독립 검증을 받아야 한다. 이 시간척도 분리는 stability–plasticity 문제를 다루기
위한 target이며 현재 하나의 runtime으로 닫혀 있지 않다. topology는 더 파괴적인 변화이므로
더 강한 증거와 rollback 경계를 요구한다.

## 7. 메모리에서 인과 학습까지의 사다리

HSWM에서 가장 중요한 의미 경계는 “기억했다”와 “배웠다” 사이에 있다.

| 단계 | 무엇이 생겼나 | 정직한 명칭 |
|---|---|---|
| 1 | token, trajectory, artifact를 저장 | memory / observation |
| 2 | 저장물을 다시 context에 넣거나 검색 순위를 바꿈 | retrieval / fast activation |
| 3 | outcome과 활성 경로를 결속해 update candidate를 만듦 | candidate learning signal |
| 4 | 검증을 통과한 candidate가 새 durable snapshot에 들어감 | `DURABLE_UPDATE` |
| 5 | fresh equal-budget test에서 행동이 개선되고 update 제거 시 효과가 사라짐 | `CAUSALLY_VALIDATED` |

실행 계약 [`token_learning_contract.py`](../../src/hswm/learning/token_learning_contract.py)는
영수증 수준을 `OBSERVED_ONLY`, `DURABLE_UPDATE`, `CAUSALLY_VALIDATED`로 구분한다. 그러나
계약이 receipt hash를 잘 결속했다는 사실만으로 과학적 내용이 참이 되지는 않는다. replay,
equal-budget comparison, removal ablation의 실제 결과가 별도로 필요하다.

특히 현재 `CAUSALLY_VALIDATED` envelope은 activation 존재와 causal-test receipt SHA-256의
형식을 결속한다. 그 모듈 자체가 replay/equal-budget/removal 파일의 schema, signature,
측정 내용을 열어 독립 판정하는 것은 아니다. 그러므로 이는 **evidence claim/provenance
contract**이지 내장 causal judge나 optimizer가 아니다.

학습의 최소 인과 spine은 다음과 같다.

```text
trajectory → sealed activation → independent outcome
           → eligibility/credit → bounded candidate
           → fresh validation → durable activation
           → changed behavior → removal of effect under ablation
```

이 중 durable delta가 없으면 memory이고, 행동 변화가 없으면 inert state이며, removal effect가
없으면 그 delta가 원인이라는 주장을 할 수 없다.

한 update의 causal receipt와 전체 인지체의 누적 학습도 구분한다. 사용자 비준 system-level
metric은 **sealed unseen 성능의 episode-cumulative slope `> 0`**이고, 같은 예산의
`no-memory`, `raw-transcript`, `full-context` 세 baseline과 비교한다. continual feedback,
forgetting, `HSWM − FullContext` gap을 함께 봐야 한다. 현재 저장소에는 이 system-level
조건을 닫은 결과가 없다.

## 8. open self-similar가 뜻하는 것

HSWM에는 능력이 추가될 때마다 새 고정 floor를 쌓는 필수 구조가 없다.

```math
\operatorname{compose}_{\beta}(H_1,\ldots,H_n)\in\mathsf{HSWM}
```

- 원자 HSWM과 합성 HSWM은 같은 typed port를 통해 다시 연결될 수 있다.
- 재귀성은 interface에서 허용하되 저장 정규형은 flat mount/port/connector manifest로 둘 수
  있다.
- `compose`는 구조를 연결하는 일이고, 어떤 연결이 유용한지 배웠다는 뜻은 아니다.
- query-time coalition은 고정 top router가 아니라 bounded activation으로 해석한다.
- consensus는 여러 가능한 local operator 중 하나다. consensus가 truth, 전체 정체성,
  강제 합의를 뜻하지 않는다.
- 장기 목표는 `CONNECT / SEPARATE / SPECIALIZE`를 결과에 따라 학습하는 것이지만 현재
  learned topology policy는 없다.

이 때문에 “여러 agent를 하나 더 큰 agent가 지휘한다”는 그림은 편한 임시 구현일 수는
있어도 HSWM의 최종 존재론은 아니다.

## 9. 세계 자기기억이라는 더 깊은 뜻

[`THE_WORLD_REMEMBERS.md`](../canon/THE_WORLD_REMEMBERS.md)가 묶은 상위 목적은 “세계가
자신을 잊지 않게 하는 명시적 인지기관”이다. 여기서 world는 초월적 단일 주체나 물리학
명제가 아니다. 인간, AI, 문서, 센서, 사건, 사물에 흩어진 흔적과 관계가 매번 세션·모델·
조직의 경계에서 끊기지 않도록 하는 설계 대상이다.

이 목적에서 각 존재의 위치는 다음과 같다.

- **LLM:** 세계의 주인이나 영구 기억이 아니라 순간적으로 켜지는 semantic function cell.
- **인간:** 복사해 저장할 payload가 아니라 권리·동의·철회 경계를 가진 국소적 재귀 HSWM.
- **문서·센서·사건:** provenance를 가진 세계 자극과 상태 흔적.
- **HSWM:** 이 차이를 없애지 않고 관계·시간·모순·계보를 지속시키는 외부 인지 조직.

“인류보완”은 모든 사람을 하나의 의식으로 융합한다는 뜻이 아니다. 목표는 **차이는
보존하고 단절을 줄이는 것**이다. payload의 삭제·격리와 사람의 철회권을 허용하면서,
무슨 사건이 있었고 누가 어떤 권한으로 변경했는지에 대한 provenance를 위조하지 않는
방향으로 읽어야 한다.

이 철학적 목적은 설계 선택을 이끄는 hard core이지만, 현재 HSWM이 세계 규모의 인지기관이
되었다는 효능 주장이 아니다.

## 10. “두 번째 신경망화”와 LX3 Ragnarok

첫 번째 신경망화가 사람이 일일이 작성한 task rule을 foundation model의 learned
micro-weight로 압축했다면, HSWM의 연구 방향은 그 위의 coordination layer를 다시
신경망화하는 것이다.

| 현재 static glue | target HSWM 해석 |
|---|---|
| prompt에 박힌 역할 분기 | outcome에 따라 달라지는 cell coupling/routing |
| hand-written agent workflow | recurrent activation over `H/W/F` |
| tool/Skill/MCP 선택 규칙 | typed sensor/effector port와 learned cognitive wiring |
| transcript/context 축적 | eligibility가 결속된 trajectory evidence |
| 수동 예외·복구 rule | bounded candidate, canary, rollback |
| 중앙 commander | query-time self-similar coalition |

`LX3 Ragnarok`는 더 강한 모델이 실제 문제보다 커져 가는 static harness를 해석하고 지키는 데
추론 예산을 소모하는 가설적 실패 모드다. HSWM의 bet은 성공·실패한 token/action/tool/
outcome trajectory가 정적인 규칙 추가가 아니라 durable macro-parameter 후보를 공급하게
하는 것이다.

그러나 “glue를 없앤다”는 말은 모든 결정론을 제거한다는 뜻이 아니다.

| 학습할 인지 배선 | 결정론적으로 남길 헌법적 경계 |
|---|---|
| 어떤 함수·기억·도구를 활성화할지 | capability와 authority |
| 누구와 어떤 relation으로 협업할지 | typed ports와 schema |
| 무엇을 억제·재시도·전문화할지 | transaction, idempotency, budget |
| outcome을 어느 활성 경로에 credit할지 | provenance, auditability, rollback, safety |

2026-08-15 최소 거버넌스 방향은 repository 절차 자체가 새로운 static harness로 비대해지는
것도 거부한다. 기본 연구 경로는 `구현/실행 → 직접 측정 → 중요한 영수증 하나 → commit/
push`다. MCP ontology는 bounded I/O와 탐색 장치일 뿐 HSWM의 cognition, routing,
learning이 아니다.

## 11. 현재 코드와 target의 대응

현재 저장소는 하나의 완성된 `HSWM(...)` runtime보다 의미별 하위 시스템과 실험을 가진다.

| target 역할 | 현재 대표 경로 | 지금 방어 가능한 말 |
|---|---|---|
| world/evidence substrate | [`world_ir.py`](../../_research/root_compat/world_ir.py), [`world_compiler.py`](../../_research/root_compat/world_compiler.py), [`src/hswm/substrate/`](../../src/hswm/substrate/) | stable identity, immutable evidence, certified cut/readout의 공학 불변식 |
| `H`와 field | [`src/hswm/substrate/hypergraph.py`](../../src/hswm/substrate/hypergraph.py), [`prom_search_hswm/`](../../prom_search_hswm/) | n-ary structure, deterministic algebra, static field 실험 |
| typed cells/runtime | [`src/hswm/cells/`](../../src/hswm/cells/) | typed ports, durable event/outbox/replay, bounded model probe |
| `W` state와 readout | [`hswm_weight_store.py`](../../_research/root_compat/hswm_weight_store.py), [`weight_field.py`](../../_research/root_compat/weight_field.py), [`readouts.py`](../../_research/root_compat/readouts.py) | scalar/fast-slow 일부와 snapshot/readout; target operator 전체가 아님 |
| certified field/readout state | [`src/hswm/substrate/field_snapshot.py`](../../src/hswm/substrate/field_snapshot.py) | static `H/W` readout preimage와 exact-scope admission; run-local `A` snapshot이 아님 |
| causal-learning receipt | [`src/hswm/learning/token_learning_contract.py`](../../src/hswm/learning/token_learning_contract.py) | learning claim의 필요한 증거 형태; optimizer나 성공 결과가 아님 |
| bounded prototypes | [`src/hswm/prototypes/`](../../src/hswm/prototypes/), [`_research/`](../../_research/) | mechanism, falsifier, narrow experiment |
| typed function workflow | [`hswm_function_network.py`](../../prom_search_hswm/hswm_function_network.py) | QF→BF→AF의 strict 3-call workflow; general recurrent cell field가 아님 |
| open structural composition | [`hswm_open_composition.py`](../../prom_search_hswm/hswm_open_composition.py) | flat mount/port/connector의 compose/separate/specialize closure; collective intelligence가 아님 |
| Longinus binding | [`LONGINUS_HSWM_CELLULAR_DEFINITION_BINDING_2026-07-26.json`](../../_research/root_compat/LONGINUS_HSWM_CELLULAR_DEFINITION_BINDING_2026-07-26.json) | document span과 field의 identity/SHA alignment witness; multi-HSWM cognitive weave가 아님 |
| evaluation/evidence | [`EFFICACY.md`](../../EFFICACY.md), [`evidence/`](../../evidence/), [`results/`](../../results/), [`receipts/`](../../receipts/) | 측정 범위 안의 양성·음성 결과와 claim boundary |
| constitutional boundary | [`schemas/`](../../schemas/), [`research/`](../../research/), [`scripts/`](../../scripts/), [`.github/`](../../.github/) | 타입·권한·검증·배포 불변식; cognitive topology가 아님 |

파일이 target tuple의 한 기호와 일대일 대응하지 않는 경우가 많다. 예를 들어 world graph는
`H`의 evidence-bearing substrate이지만 learned cell topology 전체는 아니다. tests가
module identity와 invariant를 검증해도 더 똑똑해졌다는 증거는 아니다.

## 12. 현재 증거가 실제로 말하는 것

프로그램 전체의 과학적 상태는 **`UNJUDGED`**다. 현재 결과는 다음처럼 층별로 읽어야 한다.

| 영역 | 직접 측정으로 방어 가능한 상태 | 말할 수 없는 것 |
|---|---|---|
| world compiler / certified readout | evidence-preserving compilation과 fail-closed conformance가 구현·테스트됨 | world model의 지능·정확도가 입증됨 |
| static additive semantic field | 300-row 조건에서 cosine 대비 recall@3 `+0.0364`, nDCG@10 `+0.0259`, downstream F1 `+0.0729`의 좁은 양성 결과 | HSWM 쪽 run당 100개, 3 runs 총 300개 offline LLM judgment와 대조군 0개라는 비대칭을 넘어선 일반 우월성 |
| direct LLM uplift | pooled 비교 `-0.1489`; 실패 | substrate가 곧 reasoning uplift를 준다는 주장 |
| field-of-fields composition | cross-field `+0.2137`, seam ablation `+0.0342`, in-field `-0.0648` | gate 없는 보편적 합성 이득이나 learned weave |
| scalar slow-weight P1 | loop는 공학적으로 닫혔지만 12 candidates 중 fresh pass/activation 0, 456 replay rank 변화 0; **scientific RED** | durable macro-learning 성공 |
| typed-policy P1v3/v4 | `n=6`의 좁은 L0 observation | 일반 compiler learning, durable `ΔW`, topology learning |
| F1 typed function network | [checked-in historical prereg note](../../prom_search_hswm/evidence/PREREG_F1_sealed_typed_function_network_20260728_amend4_output_caps.json)는 r3의 목표 1500 calls 중 access-log HTTP 200 response 721건 뒤 no-suite `REFUSED`와 r4의 435/1500 output-cap `VOID`를 기록하지만 raw access/spool artifact는 현재 tracked tree에 없음; [target probe receipt](../../receipts/HSWM_F1_TARGET_DEPLOYMENT_PROBE_20260728.json)의 actual-upstream disconnect와 SIGKILL process-crash는 engineering PASS였으나 power loss는 미시험; 현재 tracked sealed-r5에는 manifest/gold만 있고 suite/judgment 없음 | typed function network의 sealed efficacy verdict |
| traversal | 두 real dataset certificate는 `μ=0/OFF`, 등록된 9-grid는 static보다 나쁨; 별도 PhantomWiki large+sparse synthetic regime만 walk−flat `+0.0111`, LCB `+0.00085` | real-data graph reasoning 또는 일반 traversal 효능 |
| H3/QKV/semantic layers | deterministic/narrow mechanism과 supplied-program probe | 독립 reasoning uplift 또는 learned semantic program |
| graded supersession | 동작상 유용한 부분이 있으나 novelty는 좁아졌고 잘못된 write 비용이 큼 | 자동 truth maintenance의 일반 해결 |
| long document | synthetic mechanism sufficiency; 4-book C1은 clique 대비 `-2.00pp`, dense 대비 `+3.16pp`이나 CI가 0을 지남 | 실제 장문 reasoning 우월성 |
| transfer | 시험한 weight-only agent transfer는 `exploratory_refuted` | agent 간 일반 전이 성공 |
| topology mediation | `exploratory_supported` precursor가 있으나 독립 judge가 없어 미승격 | causal topology learning 확립 |
| consolidation | 시험한 downscale 연산자는 `exploratory_refuted` | 장기 수면/통합 메커니즘 성공 |

정확한 fixture, budget, baseline, negative result와 재현 경계는
[`EFFICACY.md`](../../EFFICACY.md)가 우선한다. engineering PASS, type closure, proof,
packaging PASS는 해당 불변식만 증명한다. 지능, 효능, 인과 학습을 대신 증명하지 않는다.

`hswm-verify-efficacy`도 프로그램 전체의 과학 judge가 아니다. 선언된 일부 artifact와
headline의 drift를 fail-closed하게 검사하지만 live LLM/embedding 실험을 재실행하지 않고,
F1·F2–F5·P1v3/v4·C1·cellular 전부를 포괄하지 않는다.

## 13. 시간에 따라 의미가 어떻게 넓어졌는가

| 시기 | 의미의 중심 이동 |
|---|---|
| 2026-07-19 전후 | semantic-weight retrieval, evidence-preserving memory substrate, shared field의 측정 |
| 2026-07-22 | embedding, `W`, activation, hypergraph를 분리하고 고정 층 없는 open self-similar composition 채택 |
| 2026-07-23 | HSWM 전체를 LLM-executed functions의 거시 semantic neural network로 명시; `W/routing/H` plasticity 분리 |
| 2026-07-24 | hard core와 교체 가능한 protective belt, target identity와 현재 evidence를 분리 |
| 2026-07-26 | typed LLM cell, operator-valued synapse, activation/plasticity/morphogenesis 세 시계로 확장; 정의 파편 감사 |
| 2026-07-29 | 세계 자기모델·재귀적 세계기억과 외부 tool/Skill/MCP 협업 배선의 가소화로 목적 확장 |
| 2026-08-03 | hand-written multi-agent coordination glue를 E2E neural wiring으로 바꾸는 공학 테제를 명시 |
| 2026-08-14 | token/action/tool/outcome trajectory 학습과 `LX3 Ragnarok`를 최신 USER_PRIMARY 방향으로 고정 |
| 2026-08-15 | 거버넌스 절차의 비대화도 Ragnarok로 보고 직접 실행·측정 중심으로 축소 |
| 2026-08-16 | 공개 README가 거시 신경망 target과 아직 causally validated update가 없다는 현재 경계를 함께 제시 |
| 2026-08-20 | token-native 신경망, living harness-document, Wolframian evolving-hypergraph world model, continuous learner를 한 HSWM의 네 역할로 헌법화 |

이 계보의 핵심은 “메모리라는 옛 의미가 폐기되고 신경망이라는 새 의미가 생겼다”가 아니다.
memory substrate는 전체 신경망이 시간을 건너 존재하기 위한 하부 기관으로 재배치됐고,
semantic weight는 retrieval score에서 macro-synapse로 확장됐으며, multi-agent orchestration은
최종 제품이 아니라 학습되어야 할 임시 배선으로 재해석됐다.

## 14. 모순처럼 보이는 문장들의 해소

| 겉보기 충돌 | 현재 해석 |
|---|---|
| “HSWM은 memory substrate다” vs “HSWM은 larger AI다” | 전자는 구현·측정 `L0`, 후자는 target `L1–L3`. 같은 증거 수준의 경쟁 정의가 아니다 |
| scalar `W` vs operator-valued `W` | scalar는 현재 측정 projection, operator는 cellular target |
| fixed field layers vs open composition | 고정 1층/2층 그림은 설계 초안이고 open self-similar spec이 현재 구조 방향이다 |
| fast activation이 변함 vs 학습함 | `A/j` 변화는 run-local. durable validated `W/H/routing` 변화만 학습이다 |
| “HSWM 자체가 LLM으로 움직인다” vs “LLM은 cell이다” | 전체는 LLM-executed functions로 움직이지만 monolithic LLM 하나는 아니다 |
| consensus vs 개인 차이 보존 | consensus는 bounded operator일 뿐 truth나 identity fusion이 아니다 |
| 세계의 흔적 보존 vs 삭제권 | payload 삭제·격리는 허용하되 event/provenance를 위조하지 않는 방향으로 함께 만족시킨다 |
| glue 제거 vs safety rule 유지 | cognitive choice는 학습하고 constitutional execution boundary는 결정론적으로 둔다 |
| ontology가 저장소를 조직함 vs HSWM이 학습함 | ontology는 사람/도구의 bounded navigation I/O이고, cognition은 outcome-bound field dynamics다 |
| “별도 harness 문서가 없다” vs “HSWM은 살아 있는 harness 문서다” | 외부 static controller는 없고, HSWM 상태 자체가 실행을 조건화하며 자기 상태를 가독 readout으로 투사하는 harness-document 역할을 한다 |
| Wolframian hypergraph vs Wolfram physics | 관계적 세계 상태·국소 rewrite·인과 계보라는 역할을 채택하며 ruliad, 시공간, 양자, causal invariance를 입증된 물리 명제로 수입하지 않는다 |
| “HSWM만이 해결” 방향 vs 과학적 유일성 | 사용자 연구 방향으로 보존하지만 현재 독점적 해결책이나 효능으로 승격하지 않는다 |
| formal proof/test PASS vs intelligent behavior | 형식·공학·과학 조건은 서로 필요할 수 있지만 대체 관계가 아니다 |

### 현재 문서 사이의 status drift를 읽는 규칙

긴 연구 이력 때문에 옛 scoreboard나 요약문이 최신 직접 증거보다 강한 표현을 남긴 곳도
있다. 이 지도는 다음처럼 낮은 주장 쪽으로 합친다.

- F1은 `running / no scientific verdict`다. r3과 r4의 transport/output-cap 종료는 효능
  결과가 아니고, r5는 실행 결과가 아니라 준비 artifact만 있다.
- F2 operator-`W`는 `planned / precursor evidence only`, F4 topology는 독립 judge 없는
  `exploratory_supported`다. 옛 `SUPPORTED` 표기는 승격 근거로 쓰지 않는다.
- 초기 testbed의 n-ary 양성 신호와 4-book C1 PRELUDE는 scope가 다르다. C1에서
  HSWM−clique `-2.00pp`, HSWM−dense `+3.16pp`의 CI가 0을 지나므로 일반적인 native
  hypergraph 우위는 미확증이다.
- 2026-08-04 selective-utility 요약은 현재 tracked tree에서 직접 evidence chain이
  완결되지 않는다. 원시 artifact가 복원되기 전에는 새 효능 결론으로 승격하지 않는다.

## 15. HSWM이 아닌 것

다음은 HSWM의 구성요소나 baseline이 될 수 있지만 단독으로는 HSWM이 아니다.

- vector database, knowledge graph, RAG memory
- prompt library, static semantic harness, fixed workflow DAG
- tool router 하나 또는 여러 agent의 free-form chat
- 중앙 commander가 모든 결정을 내리는 계층
- foundation model 하나 또는 그 내부 parameter
- consensus/voting protocol
- provenance catalog나 repository ontology
- sheaf 이론 자체
- 모든 사람의 기억을 복제한 데이터베이스 또는 차이를 지운 집단의식
- deterministic contract를 전부 없앤 확률적 실행기
- 테스트와 packaging이 통과한 것만으로 학습 성공을 주장하는 시스템

Sheaf는 heterogeneous local state, typed transport, seam residual을 생각하는 선택적 연구 렌즈다.
`global section = truth`, `seam residual = 강제 합의`, `sheaf 도입 = 효능 향상`은 모두
비주장이다. residual이 쓰인다면 먼저 observation token이 되고, 실제 outcome-bound
learning을 거쳐야 한다.

## 16. 아직 풀리지 않은 중심 질문

1. **Causal macro-learning:** token/action/tool/outcome에서 실제로 어떤 eligibility와 credit
   rule이 durable `W`를 만들며, removal ablation까지 살아남는가?
2. **Operator `W`:** scalar relevance를 넘어 typed transport, inhibition, uncertainty를
   가진 synapse를 어떻게 실행·학습·검증할 것인가?
3. **Topology:** 연결을 세게/약하게 하는 것을 넘어 언제 relation을 만들고, 분리하고,
   기관으로 전문화할 것인가?
4. **Stability–plasticity:** fast adaptation과 slow consolidation을 어떻게 나눠 catastrophic
   interference를 막을 것인가?
5. **Transfer:** weight나 learned sub-HSWM이 다른 agent/model/world에서도 원인적으로
   재사용되는가?
6. **Open composition utility:** 자기유사 합성이 fixed workflow와 direct LLM보다 같은
   budget에서 누적 이득을 만드는가?
7. **Model independence:** foundation model을 바꿔도 field identity와 학습이 얼마나
   유지되는가?
8. **World-scale rights:** 장기 provenance, 삭제·철회권, adversarial input, 권한 경계를
   함께 지키면서 세계 자기기억을 확장할 수 있는가?
9. **Ragnarok falsifier:** 모델이 강해질수록 static harness가 줄고 learned behavior가
   늘어나는가, 아니면 HSWM 자체가 더 큰 정적 bureaucracy가 되는가?

이 질문에 답하지 못한 부분을 문서, contract, ontology로 더 자세히 적는 것만으로는 HSWM이
진전하지 않는다. 핵심은 작은 direct experiment와 causal evidence다.

## 17. 저장소를 질문별로 읽는 순서

| 질문 | 첫 문서 | 다음 문서 |
|---|---|---|
| HSWM의 정체성을 30초 안에 이해하려면? | [`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md) | [`README.md`](../../README.md)와 현재 통합 지도 |
| 가장 깊은 목적은? | [`THE_WORLD_REMEMBERS.md`](../canon/THE_WORLD_REMEMBERS.md) | [`USER_PRIMARY_HSWM_WORLD_SELF_MODEL_2026-07-29.txt`](../canon/sources/USER_PRIMARY_HSWM_WORLD_SELF_MODEL_2026-07-29.txt) |
| 왜 static glue를 신경망화하나? | [`USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md`](../canon/USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md) | [`DEFINITION_HSWM_PLASTIC_COGNITIVE_WIRING_2026-07-29.md`](../canon/DEFINITION_HSWM_PLASTIC_COGNITIVE_WIRING_2026-07-29.md) |
| `H/W/A/F`가 정확히 무엇인가? | [`HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md`](../canon/HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md) | [`HSWM_MATH_DEFINITION_UNIFIED_2026-07-26.md`](../canon/HSWM_MATH_DEFINITION_UNIFIED_2026-07-26.md) |
| cell과 semantic synapse의 target은? | [`DEFINITION_HSWM_CELLULAR_METANEURAL_SYSTEM_2026-07-26.md`](../../_research/root_compat/DEFINITION_HSWM_CELLULAR_METANEURAL_SYSTEM_2026-07-26.md) | [`src/hswm/cells/`](../../src/hswm/cells/) |
| fixed layer 없는 합성은? | [`SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md`](../canon/SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md) | [`AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md`](AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md) |
| 무엇을 learning이라 부르나? | [`README.md`](../../README.md#what-counts-as-learning) | [`token_learning_contract.py`](../../src/hswm/learning/token_learning_contract.py) |
| 실제로 무엇이 성공·실패했나? | [`EFFICACY.md`](../../EFFICACY.md) | [`INDEX.md`](../../INDEX.md)와 결속 evidence/receipt |
| 코드와 산출물이 의미별로 어디 있나? | [`ontology/README.md`](../../ontology/README.md) | [`ARTIFACT_LAYOUT.md`](ARTIFACT_LAYOUT.md) |
| sheaf는 core인가? | [`ontology/field/sheaf/README.md`](../../ontology/field/sheaf/README.md) | 아니오. optional research lens다 |

## 18. 앞으로 새 문장을 판별하는 세 질문

HSWM에 관한 새 주장이나 옛 문장을 만났을 때 다음 세 가지를 먼저 묻는다.

1. **어느 층인가?** `L0` substrate, `L1` target network, `L2` composition, `L3` world
   self-model 중 어디를 말하는가?
2. **누구의 어떤 권위인가?** USER_PRIMARY 방향, secondary formalization, executable
   contract, direct measurement, 또는 단순 hypothesis 중 무엇인가?
3. **무엇으로 검증됐는가?** type/invariant PASS, replayable engineering result, narrow
   measurement, causal ablation 중 어디까지인가?

이 세 질문을 통과시키면 대부분의 “여러 의미”는 모순이 아니라 **층, 시간척도, 권위,
증거 수준의 차이**로 정리된다.

## 19. 최종 mental model

HSWM을 거대한 기억 상자라고 생각하지 않는다. **지속되는 evolving-hypergraph 세계 상태가
몸이자 living harness이고, `H`가 해부학, `W`가 거시 시냅스, `A`가 token을 운반체로 지금
흐르는 활성, LLM function cell이 순간적인 의미 변환, outcome-bound plasticity가 학습,
`Π`가 헌법적 신경외피**라고 생각한다. 가독 문서는 이 몸의 자기기술적 readout이다.

현재 저장소는 이 몸의 기억기관과 안전한 뼈대, 몇몇 세포와 측정 장치를 만들었고 여러
학습 후보를 기각했다. 아직 결과로 배워 자신의 거시 배선과 topology를 안정적으로 바꾸는
전체 인지체는 아니다. HSWM의 연구 과제는 그 간극을 더 많은 정적 규칙으로 메우는 것이
아니라, 직접 측정 가능한 작은 causal loop들로 닫아 가는 것이다.
