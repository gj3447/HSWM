# HSWM canonical research direction — 2026-07-24

## 1. 버리지 않는 hard core

HSWM은 **Hypergraph Semantic Weight Map**이다. 목표는 LLM을 단순 호출 도구나
검색기의 마지막 답변기로 붙이는 것이 아니라, LLM 호출 자체를 거대한 하이퍼그래프
신경망의 **semantic activation/transition function**으로 사용하는 것이다.

\[
\mathrm{HSWM}_t=(H_t,W_t,A_t,F_t),\qquad
a_i^{t+1}=f_i^t(x_i^t,a_{\mathcal N(i)}^t;W_t),\qquad
f_i^t:=\operatorname{LLM}(\rho_i,\tau_i,\cdot)
\]

- `H_t`: 의미 상태와 함수 노드를 n-ary relation으로 결합하는 가변 hypergraph.
- `W_t`: 어떤 semantic bond가 활성화되고 억제되며 전달되는지를 정하는
  **Semantic Weight Map**. 모델 내부 파라미터와 구별되는 macro-synaptic weight다.
- `A_t`: 시간에 따라 전달되는 activation, working state, recurrent state.
- `F_t`: typed input/output port와 역할 `rho_i`를 가진 LLM-executed semantic functions.

여기서 “LLM이 activation function이다”는 말은 LLM을 ReLU 같은 scalar 비선형 함수라고
부르는 것이 아니다. **macro-neuron/function node가 입력 semantic state를 다음 semantic
activation으로 변환하는 연산자**라는 뜻이다. 하나의 foundation model이 여러 역할 노드를
실행할 수 있으며, 신경망의 고유 상태와 학습 대상은 모델 파라미터만이 아니라 `H`, `W`,
`A`, typed routing 전체다.

따라서 HSWM을 다음으로 축소해서는 안 된다.

- LLM + 외부 vector memory;
- 일반적인 KG-RAG wrapper;
- 여러 agent를 순서대로 호출하는 workflow;
- prompt graph만 있고 persistent semantic weight가 없는 orchestration.

CAS, provenance, replay, CRDT, typed validation은 중요한 deterministic control plane이지만
그 자체가 semantic neural substrate는 아니다. HSWM의 neural claim은 activation이 실제
bond를 통과하고, outcome credit이 `W`를 바꾸며, 바뀐 `W`가 이후 행동과 다른 agent의
활성화를 바꿀 때 성립한다.

## 2. 바꿔도 되는 protective belt

hard core를 보존하면서 다음 구현은 실험 결과에 따라 교체할 수 있다.

- TF-IDF/dense embedding/candidate generator;
- 구체적인 prompt 문구와 역할 수;
- 특정 LLM과 tokenizer;
- bond potential parameterization과 normalization;
- hyperedge proposal policy와 topology-edit policy;
- replay/storage/transport 구현;
- benchmark와 evaluator.

F1에서 vector baseline과 동률이었다고 hard core를 폐기하지 않는다. 그것은 현재
candidate features와 3-function protective belt가 아직 고유 이득을 만들지 못했다는
결과다. 반대로 typed workflow가 한 번 이겼다는 이유만으로 hard core가 입증됐다고도
하지 않는다.

## 3. 2026-07-24 증거 상태

| 층 | 현재 증거 | 판정 |
|---|---|---|
| evidence/compiler/replay substrate | immutable artifact, typed boundary, replay와 여러 fail-closed test 구현 | engineering mature |
| static semantic field | 일부 frozen retrieval 실험에서 positive, traversal/cognitive-uplift 등 다수 반증도 보존 | domain-conditional |
| L0 typed policy actuation | P1v3와 독립 P1v4의 작은 heldout에서 frozen-model answer 변화 재현 | narrow partial, `Delta W` 아님 |
| PROM-9 F1 LLM function network | 실제 Qwen3.6-27B 60호출: typed 2/4, flat 1/4, vector 2/4, removal 0/4, shuffle 1/4 | development-only; token parity 실패; unique efficacy 없음 |
| outcome→credit→persistent weight | scalar P1의 기존 시도는 fresh gain 0; 새 typed bond loop는 미실측 | open / highest priority |
| Agent A→frozen Agent B transfer | weight-only unseen transfer 없음 | unimplemented |
| learned topology plasticity | safe gate는 있으나 gain을 만든 learned editor 없음 | open |

## 4. 단일 연구 방향

연구 순서는 넓게 확장하지 않고 다음 인과 사슬을 닫는 순서로 고정한다.

### Gate A — actual-compute-matched F1

동일 모델, 후보 universe, physical call 수뿐 아니라 실제 input/output token을 맞춘다.
sealed `n>=100`에서 typed가 flat과 vector를 모두 이기고, 역할 제거/셔플에서 효과가
사라지는지 본다. 이것은 function-network composition의 최소 gate다.

### Gate B — real Semantic Weight Map plasticity

\[
outcome\rightarrow used\ bond\ eligibility\rightarrow credit
\rightarrow \Delta W_{fast}\rightarrow validated\ W_{slow}
\rightarrow changed\ later\ activation
\]

모든 단계가 snapshot/receipt로 이어져야 한다. static update, random credit, shuffled
eligibility, no-promotion, learned-delta removal을 같은 예산으로 비교한다. learned delta를
제거했을 때 개선도 사라져야 한다.

### Gate C — weight-only multi-agent transfer

Agent A만 학습한다. Agent B의 모델, prompt, code는 동결한다. A에서 B로 전달 가능한 것은
서명된 semantic-weight/update packet뿐이며 transcript, answer, hidden cache는 금지한다.
sealed unseen 문제에서 B가 no-transfer 및 shuffled-transfer보다 좋아져야 한다.

### Gate D — topology plasticity와 recurrence

`CONNECT`, `SEPARATE`, `SPECIALIZE` 같은 hyperedge edit가 static topology보다 새 문제의
activation routing을 개선하는지 검사한다. fresh/canary/forgetting/replay gate를 모두
통과한 변경만 durable topology에 승격한다.

## 5. 중단·축소 규칙

- 공정한 F1을 두 번 독립 실행해도 typed가 vector와 동률이면 현재 3-function
  composition의 **고유 성능 주장**을 중단하고 protective belt를 교체한다.
- 두 개의 독립 P1v5 시도에서 promoted `Delta W`가 이후 bond 순위나 답을 바꾸지 못하면
  현재 weight-learning rule을 폐기한다.
- weight-only A→B가 transcript/vector transfer를 이기지 못하면 shared-field transfer
  주장을 폐기한다.

이 kill rule은 HSWM hard core 자체를 자동 삭제하지 않는다. 다만 hard core를 계속
연구하려면 새로운 protective belt와 새로운 사전등록 falsifier를 제시해야 한다. 반증된
구현을 이름만 바꿔 반복하는 것은 금지한다.

## 6. 다음 실행 한 줄

**이론 문서 추가보다 Gate A의 실제 토큰 parity를 먼저 닫고, real Gate-0 pack 뒤 Gate B의
`outcome → credit → Delta W → removal`을 닫는다. 그 뒤에만 Agent A→B transfer와 topology로
간다. 하네스는 이 순서를 건너뛰는 evidence를 거부한다.**

관련 정본:

- `CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`
- `HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md`
- `PROM_9_HSWM_LLM_FUNCTION_SEMANTIC_NEURAL_NETWORK_2026-07-24.md`
- `prom_search_hswm/docs/PROM9_F1_2WIKI_DEVELOPMENT_RESULTS_20260724.md`
- `PROM_HSWM_PLASTICITY_WEIGHT_TOPOLOGY_LEARNING_2026-07-23.md`
