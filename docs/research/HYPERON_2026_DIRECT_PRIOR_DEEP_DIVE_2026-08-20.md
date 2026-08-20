# Hyperon 2026 직접 선행 정밀 감사

> **상태:** `SECONDARY_AI_RESEARCH / PRIMARY_SOURCE_AND_PUBLIC_CODE_AUDIT`
> **기준일:** 2026-08-20
> **대상:** *Hyperon: The Open-Source Infrastructure for Artificial General
> Intelligence*, July 2026 및 TrueAGI/OpenCog/ASI Alliance 공식 공개 저장소
> **백서 SHA-256:**
> `bdb3efb266a35f10fe07addc34c9def68708b4fb123480163c724d8ceec3b5f2`
> **관계:**
> [`HSWM_TOKEN_HYPERGRAPH_SEMANTIC_WEIGHT_PRIOR_ART_2026-08-20.md`](./HSWM_TOKEN_HYPERGRAPH_SEMANTIC_WEIGHT_PRIOR_ART_2026-08-20.md)의
> Hyperon 항목을 확장하고,
> [`USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md`](../canon/USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md)의
> novelty·구현 경계를 교정한다.

## 0. 판정

**Hyperon 2026은 현재 조사 범위에서 HSWM의 가장 가까운 직접 선행이다.** 단순히
지식그래프를 LLM에 붙이는 수준이 아니라 다음 조합을 한 아키텍처 안에 둔다.

```text
typed persistent metagraph
+ executable graph program
+ weighted attention/resource allocation
+ LLM hidden-state read/write bridge
+ local predictive-coding learning
+ provenance and candidate promotion
+ causal ablation and rollback
+ private/shared/distributed cognition
```

따라서 HSWM은 `LLM + hypergraph`, 비파괴 history, provenance, LLM–graph bridge,
shared cognition의 **개념적 최초**를 주장해서는 안 된다.

그러나 Hyperon 백서는 이 전체가 완성·독립 benchmark된 시스템이라고 주장하지
않는다. 백서의 자체 성숙도 표는 MeTTa·Atomspace·MORK core만 구현 capability로,
transformer bridge·QuantiMORK는 prototype/research hypothesis로, TECAN은 specified
design/research programme으로 분류한다. 결론부도 완전 통합 architecture가 이미
배포·독립 검증·안전 증명됐다는 뜻이 아니라고 명시한다.

그러므로 판정은 네 층으로 나뉜다.

| 질문 | 판정 |
|---|---|
| Hyperon은 HSWM의 직접 **개념·아키텍처 선행**인가? | **예. 매우 강하다.** |
| 실행 가능한 metagraph·rewrite·PC 등의 **부품 선행**인가? | **예.** |
| 백서의 전체 neural-symbolic 폐루프가 공개 코드로 통합됐는가? | **확인되지 않았다.** |
| 그 통합체의 인지 효능이 독립적으로 입증됐는가? | **아니다. 백서도 그렇게 주장하지 않는다.** |

HSWM에 남는 경계는 더 좁다. 역할별 n-ary incidence를 통과하는 명시적
semantic/causal operator가 LLM token event와 **외부 outcome** 사이에서 실제로
학습되고, 그 `ΔW/ΔH`가 다음 token/action을 바꾸는 폐루프를 구현·실증하는 것이다.
현재 HSWM에도 그 neural runtime은 아직 없다.

## 1. 조사 규율

이 감사는 다음을 분리한다.

1. 백서가 설명하는 **아키텍처**;
2. 백서가 스스로 붙인 **주장 성숙도**;
3. 공식 공개 저장소에서 관찰되는 **실제 코드 범위**;
4. 관측 결과가 아니라 앞으로 확인할 **falsifiable target**.

주요 근거는 공식
[Hyperon Deep-Dive Whitepaper](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf),
[TrueAGI 공식 GitHub 조직](https://github.com/trueagi-io),
[ASI Alliance OmegaClaw 저장소](https://github.com/asi-alliance/OmegaClaw-Core),
[OpenCog AtomSpace 저장소](https://github.com/opencog/atomspace)다. PDF는 텍스트 추출뿐
아니라 핵심 표·수식·claim-status 페이지를 렌더링해 육안 확인했다.

`확인되지 않았다`는 공개 기본 branch와 공식 공개 자료에서 찾지 못했다는 뜻이다.
비공개 저장소, 미공개 branch, 개인 저장소까지 포함한 세계적 부재 주장이 아니다.

## 2. Hyperon 2026은 무엇인가

Hyperon은 하나의 모델이나 한 저장소가 아니다. 다음 층을 한 AGI infrastructure로
묶으려는 프로그램이다.

| 층 | 역할 |
|---|---|
| Atomspace / MORK | typed, content-addressed metagraph와 rewrite 실행 substrate |
| MeTTa | 프로그램·query·rewrite rule 자체를 graph로 표현하는 reflective language |
| PLN 계열 | evidence와 uncertainty를 가진 추론 |
| ECAN / TECAN | 현재 attention과 typed compute resource 배분 |
| OmegaClaw | Context Frame과 module routing을 담당하는 control fabric |
| OmegaSelf | evidence→belief→prediction→proposal→policy→action의 자기모델·governance |
| OmegaHive | individual/shared Atomspace를 가진 governed multi-agent cognition |
| transformer bridge | neural hidden state와 Atomspace의 read/write 연결 |
| QuantiMORK | tensor/neural operation 자체를 Atomspace substrate 안으로 옮기려는 장기 방향 |

이 구성이 HSWM과 가까운 이유는 memory, program, attention, learning, governance,
collective cognition을 별도 앱이 아니라 하나의 persistent cognitive metagraph 주위에
배치하기 때문이다.

## 3. persistent metagraph와 state

백서의 Atomspace는 사실뿐 아니라 procedure, neural weight, control signal을 typed
Atom으로 표현한다. MeTTa program도 Atomspace 안에 저장되는 graph rewrite rule이므로
시스템은 자신의 program과 control rule을 query·검사·수정할 수 있다
([pp. 18–19](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=18)).

MORK 방향은 content-addressed PathMap/Merkle-DAG 구조, immutable node, 새 version과
atomic delta를 통한 변경을 설명한다. Semantic Memory of State는 cognitive epoch의
link insertion과 weight modification을 checkpoint, update patch, digest, influence sketch로
기록한다
([pp. 20–23](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=20)).

World model은 세 representation을 braid한다.

- symbolic Atom/program;
- role binding을 보존하는 HMH hypervector;
- dense neural vector/tensor.

이들 사이의 grounding/lifting operator, drift와 cycle consistency까지 평가 대상으로 둔다
([pp. 34–36](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=34)).
따라서 HSWM의 canonical graph/compiled neural plane, immutable evidence, versioned state는
넓은 수준에서 이미 직접 겹친다.

## 4. weight는 하나가 아니다

Hyperon 계열의 `weight`를 하나의 semantic synapse로 읽으면 안 된다.

| 값 | 의미 | HSWM과의 관계 |
|---|---|---|
| PLN truth value | proposition을 지지하는 epistemic evidence | truth/evidence plane |
| STI/LTI | 현재 salience와 장기 attention importance | activation/scheduling plane |
| TECAN fuel | 특정 종류의 계산을 실행할 operational budget | compute-resource plane |
| policy permission | exact proposal이 실제 행동할 권한 | governance plane |
| neural/PC parameter | prediction error를 줄이는 dense/local model parameter | compiled learning plane |
| MORK traversal weight | weighted sampling·priority traversal에 쓰는 aggregate | storage/query scheduling plane |

TECAN은 operation `o`의 typed fuel vector와 rewrite `r`의 cost를 둔다.

\[
F_o \in \mathbb{N}^{|T|}, \qquad
Enabled(o,r) \Leftrightarrow Precondition(r) \land F_o \succeq \kappa_r
\]

matching, deduction, induction, abduction, revision, grounding, provenance, causal replay,
context bridge, counterfactual simulation, compression, mutation 등의 fuel이 분리된다. active
process가 자기 fuel을 발행하지 못하며 외부 evaluator가 verified progress·prediction·causal
ablation 등에 따라 mint해야 한다
([pp. 43–44, 65](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=43)).

### 4.1 반드시 피할 token 용어 충돌

| 용어 | 정확한 의미 |
|---|---|
| LLM token | transformer sequence의 subword/text position과 그 hidden state |
| TECAN token | cognitive operation을 살 수 있는 typed resource/permission credit |

HSWM 구현 명칭도 다음처럼 분리해야 한다.

```text
LLMTokenEvent / TokenActivation     # 의미·활성 carrier
ComputeCredit / AttentionBudget    # 연산 자원·실행 affordability
TruthSupport                       # epistemic support
ActionCapability                   # permission
```

## 5. LLM 통합의 세 경로

백서는 다음 migration path를 둔다
([pp. 83–84](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=83)).

1. **External Neural Space:** 기존 model runtime을 유지하고 input, output, embedding,
   selected activation, provenance를 Atom으로 기록한다.
2. **Predictive-coding / symbolic-head bridge:** open transformer의 일부 hidden state에
   graph read/write head, PC node, sparse residual column을 연결한다.
3. **Native Neural Atomspace:** tensor와 neural operation을 QuantiMORK/MORK 구조 안에
   표현하여 graph memory·attention·local update를 같은 substrate에서 수행한다.

### 5.1 token-position symbolic head

token/patch position `i`의 hidden state `h_i`에서 query를 만든다.

\[
q_i = W_q h_i
\]

query는 memory, rule, proof motif, policy, goal, Context Frame을 읽는다. 결과는
cross-attention, gated adapter, low-rank residual, predictive prior 등으로 neural state에
들어간다. 반대 방향 write head는 entity, relation, event, rule, causal hypothesis, code,
plan 후보를 만든다.

중요하게도 write는 truth가 아니라 **candidate**다. schema, deduplication, evidence link,
calibration, permission, ephemeral→shared promotion 검사를 거쳐야 한다. source text token,
image, tool result, hidden-state region도 provenance로 연결한다
([pp. 85–86](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=85)).

이는 HSWM의 token→graph activation, candidate commit, provenance와 직접 겹친다. 단,
백서가 role-bearing n-ary incidence마다 하나의 semantic/causal operator를 정의해 외부
outcome으로 갱신하는 것은 아니다.

## 6. predictive coding, recurrence, causal audit

bridge는 latent state, prediction, precision, symbolic constraint, frozen-base drift penalty가
포함된 schematic energy를 local prediction error로 줄인다. inference는 state를,
learning은 predictor parameter를 갱신한다
([pp. 86–87](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=86)).

백서는 다음도 제안한다.

- persistent error를 PLN, tool call, subgoal 생성으로 전달;
- narrow correction을 rank-one sparse residual column으로 학습;
- column/template에 name, scope, weakness, domain을 부여;
- recurrent trajectory의 causal impact를 intervention으로 평가;
- cheap surrogate를 주기적인 exact ablation으로 보정;
- benchmark→causal audit→interference test→shadow→scoped promotion→rollback.

따라서 local learning, recurrent activation, causal ablation, learned-structure promotion도
HSWM만의 넓은 독자성으로 둘 수 없다. 다만 이는 주로 specified/prototype programme이고
완전한 공개 통합 결과가 아니다.

## 7. provenance, proposal, policy, rollback

OmegaSelf는 append-only event sequence에 causal time, representation time, epistemic time을
구분한다. 중요 belief는 source event, derivation, dependency partition,
correction/retraction, content-addressed root를 포함한 replayable evidence closure를 가져야
한다. 오래된 evidence를 삭제하기보다 현재 applicability에 대한 새 assessment를 기록하고,
같은 evidence가 여러 path를 통해 중복 가산되지 않도록 identity를 유지한다
([pp. 51–52](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=51)).

LLM output은 typed immutable proposal이 되고 별도 policy gate가 그 exact proposal에
`Allow`를 발행해야 실행된다. rollback은 과거를 지우는 복원이 아니라 intervening
history를 보존하는 새 directed continuation이다
([pp. 54–56](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=54)).

결론적으로 비파괴 history, supersession, provenance, exact proposal authorization,
rollback도 HSWM의 단독 novelty가 아니다. 오히려 HSWM이 Hyperon에서 강하게 수입해야
할 안전 계약이다.

## 8. shared/private cognition과 확장

백서는 state를 무조건 하나의 global graph나 chain에 넣지 않는다.

- local Atomspace: private working memory와 scratch/control state;
- DAS Atomspace: durable knowledge와 cross-node state;
- chain-backed state: model/rule promotion, governance decision 등 고가치 검증 기록.

OmegaHive는 shared Atomspace와 agent별 individual Atomspace를 함께 사용하고, shared
write에는 provenance를 요구한다. collective view가 개별 identity와 evidence closure를
뭉개지 않아야 한다
([pp. 45–47](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=45)).

이는 인류보편체를 구현할 때에도 중요한 교정이다. `하나`는 모든 private state를
평탄화하는 단일 DB가 아니라, local sovereignty와 shared evidence closure가 typed
boundary로 연결되는 하나의 인지 구조여야 한다.

## 9. 백서가 스스로 밝힌 성숙도

백서의 claim vocabulary는 다음과 같다: implemented capability, prototype, specified
design, research hypothesis, illustrative target, externally validated. Table 1의 핵심은
다음과 같다
([pp. 16–17](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=16)).

| subsystem | 백서의 baseline status | 정확한 해석 |
|---|---|---|
| MeTTa, Atomspace, MORK core | implemented capability | 공개 작동 부품은 있으나 성능·운영 범위는 version/workload 의존 |
| DAS, RSpace/Rholang, ASI:Chain | implemented capability / prototype | core 기술과 end-to-end deployment profile을 구분 |
| PRIMUS | implemented components / specified design | 일부 algorithm은 작동, 연속 통합 architecture는 programme |
| OmegaClaw | prototype / active implementation | 기능을 점진 구현·시험 중 |
| OmegaSelf | specified design / prototype components | full deployment·validation은 단계적 과제 |
| OmegaHive | experimental prototype | solved collective intelligence 주장이 아님 |
| transformer bridge, QuantiMORK | prototype / research hypothesis | deeper PC/symbolic/native integration은 staged ablation 필요 |
| ωPLN, TECAN, STLM, semantic chemistry | specified design / research programme | broad performance claim은 benchmark 필요 |
| fluid/geometry/TransWeave 등 | research hypothesis / specified design | proof obligation과 empirical validation 필요 |

결론부는 전체 architecture가 이미 배포·독립 benchmark·안전 증명됐다는 주장이
아니라고 다시 못 박는다
([p. 122](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=122)).

### 9.1 백서의 neural bridge는 아직 실험 사다리다

pp. 93–95는 frozen 1B–7B baseline에서 시작해 read-only symbolic head, PC overlay,
sparse residual column, controlled loop, controller column, validated closed read/write,
OmegaClaw/PRIMUS integration으로 올라가는 staged programme을 둔다. task score뿐 아니라
calibration, false graph write, provenance completeness, PC convergence, drift, causal
ablation, retention, latency·memory·energy, fallback·rollback을 함께 측정하라고 한다
([pp. 93–95](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=93)).

p. 127–128의 world-model·TECAN 우위 문장도 관측 결과가 아니라 falsifiable target이다.
즉 백서가 제안하는 비교 실험을 실제 결과로 잘못 인용해서는 안 된다
([pp. 127–128](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf#page=127)).

## 10. 공식 공개 코드 감사

2026-08-20의 공식 공개 기본 branch를 기준으로 한 판정이다.

| 공개 구현 | 확인한 실제 범위 | 통합체에 대해 증명하지 않는 것 |
|---|---|---|
| [hyperon-experimental `v0.2.10`](https://github.com/trueagi-io/hyperon-experimental/tree/3f76dc460da6961f57f69f6c3e550c59c74ada83) | Rust core, MeTTa interpreter/REPL, typed Atom/Space API, C/Python binding, DAS integration test 경로. README는 active pre-alpha, release는 prerelease | Classic AtomSpace 전체와 동일한 구현도 아니며 Omega*·TECAN·token-position symbolic head·PC bridge 전체도 아님 |
| [DAS](https://github.com/singnet/das) | 분산 query/storage/service bus, Redis/Mongo/MORK adapter, context별 scalar STI, pairwise Hebbian attention/query evolution | 전 세계의 강일관 shared cognition이나 LLM-token·role-aware n-ary outcome credit가 아님 |
| [MORK](https://github.com/trueagi-io/MORK) | Rust PathMap/hypergraph/MeTTa kernel, query/rewrite, CLI와 differential corpus harness | release/공식 CI가 없고 백서의 Weighted Atom Sweep·ShardZipper·ByteFlow 공개 main 구현은 확인되지 않음 |
| [FabricPC `v0.4.0`](https://github.com/trueagi-io/FabricPC/tree/138941ef5763ab202c7df07879d3f21678e6cc0a) | JAX PC library; arbitrary/recurrent/cyclic graph, transformer와 token loader, node-local learning, PC-vs-backprop 비교 | source에서 MeTTa·Atomspace·MORK 연결을 찾지 못함; provenance promotion·TECAN loop 증거도 아님 |
| [pln-experimental](https://github.com/trueagi-io/pln-experimental) | MeTTa/Hyperon PLN chaining과 truth-value experiment | 백서의 ωPLN 전체나 통합 cognition |
| [OmegaClaw-Core](https://github.com/asi-alliance/OmegaClaw-Core/tree/00fd6c5b3acb31e7df310267e78413d0020d1bee) | Hyperon/PeTTa 위의 실행 가능한 agent prototype; MeTTa loop, 외부 LLM provider, ChromaDB `remember`, channel·plugin·test 구조 | internal transformer symbolic head, verified provenance→shadow→promotion, TECAN, QuantiMORK, OmegaSelf/Hive 전체 |
| [OpenCog sensory/Ollama adapter](https://github.com/opencog/sensory/tree/64849f34366339af0b57fddf17e111566bae4c20/opencog/atoms/ollama) | 외부 model의 generate/chat/embed 호출과 embedding test | 단순 API/FFI adapter이며 transformer 내부 hidden state bridge가 아님 |
| [Hyperon Torch grounding test](https://github.com/trueagi-io/hyperon-experimental/blob/3f76dc460da6961f57f69f6c3e550c59c74ada83/python/integration/test_torch.py) | tensor가 grounded Atom을 통과한 뒤에도 autograd와 loss 감소가 유지됨 | 파일 자체가 full MeTTa+Torch integration이 아니라고 한정; symbolic head나 token credit loop가 아님 |
| [OpenCog AtomSpace](https://github.com/opencog/atomspace) / [Classic ECAN](https://github.com/opencog/attention) | 성숙한 C++ generalized metagraph DB/query/rewrite와 별도 STI/LTI·diffusion·Hebbian 구현 | 새 Hyperon Rust Space와 별도 계보이며 Hyperon 2026 neural bridge/outcome learning이 아님 |

TrueAGI 조직만 검색하면 `OmegaClaw` 이름의 저장소가 나오지 않지만, 관련 공식 공개
구현은 ASI Alliance 조직의 `OmegaClaw-Core`에 존재한다. 반면 감사일 현재 공식 공개
surface에서 `OmegaSelf`, `OmegaHive`, `TECAN`, token-position `Symbolic Head`,
`QuantiMORK` 이름의 독립 통합 구현은 확인하지 못했다. 이는 이름 그대로의 공개
repo/기본 branch 관찰이며, 다른 repo 내부나 비공개 work의 부재를 뜻하지 않는다.

공개 코드에서 가장 가까운 **작동 attention 선행**은 DAS AttentionBroker다. 하지만
그것은 context별 scalar STI와 pairwise co-occurrence Hebbian network로 query 후보를
우선화하는 시스템이다. HSWM target의 LLM token event, role-aware n-ary incidence,
external-outcome credit, 비파괴 claim provenance가 한 객체로 결합된 것은 아니다.

또한 immutable Atom, append history, graph frame 같은 저수준 부품이 존재한다는 사실만으로
백서의 OmegaSelf식 evidence closure, 검증, shadow promotion, rollback pipeline이 구현됐다고
간주하지 않았다. 공식 공개 core에서 이 end-to-end 상태기계와 test는 찾지 못했다.

### 10.1 실행 확인

공식 release와 source tag의 kernel 범위는 실제로 실행했다.

| 대상 | 실행 | 결과 | 경계 |
|---|---|---|---|
| PyPI `hyperon==0.2.10` | MeTTa `!(+ 2 3)`와 Atomspace `(parent alice bob)` pattern match | `[[5]]`, `[[alice]]`; exit `0` | interpreter와 Space query smoke test일 뿐 LLM/TECAN/Omega test가 아님 |
| `hyperon-experimental` `v0.2.10`, commit `3f76dc460da6961f57f69f6c3e550c59c74ada83` | `cargo run -p hyperon --no-default-features --features pkg_mgmt --example sorted_list`와 `custom_match` | 내장 assert와 binding output 통과; exit `0` | rewrite/matcher kernel만 확인 |
| 같은 source의 default `metta-repl` build | default dependency build | host에 `protoc`가 없어 `metta-bus-client` build 단계 중단 | code defect 판정이 아니라 감사 host prerequisite 미충족 |

Python smoke test는 project environment를 건드리지 않는 isolated environment에서
다음 계약으로 재확인했다.

```text
hyperon 0.2.10
arithmetic == [[5]]
graph_query == [[alice]]
exit == 0
```

### 10.2 코드와 백서가 함께 말해 주는 것

1. **실체 없는 백서는 아니다.** MeTTa, Space/Atom API, MORK, PLN, PC framework라는
   실행 가능한 부품과 오랜 AtomSpace 계보가 있다.
2. **한 번에 실행되는 완성 Hyperon AGI도 아니다.** 공식 public surface에서 백서의
   전체 Omega/TECAN/neural bridge loop를 재현할 단일 release·benchmark package는
   확인되지 않았다.
3. **부품 존재와 synergy 증명을 혼동하면 안 된다.** A, B, C가 각각 실행된다는 사실은
   `A+B+C`가 안정적으로 학습하고 성능을 낸다는 증거가 아니다.
4. **공개 end-to-end benchmark가 경계다.** 고정 LLM 대비 Atomspace + attention +
   provenance + learning을 함께 켠 versioned benchmark package는 찾지 못했다.

## 11. HSWM과의 1:1 비교

| HSWM 축 | Hyperon 2026 | 현재 HSWM | 남은 정직한 경계 |
|---|---|---|---|
| `H`: persistent n-ary topology | typed Atomspace/MORK metagraph와 version 방향 | evidence/world graph와 boolean incidence 구현; role-aware learned topology는 target | role-bearing incidence와 outcome-governed `ΔH`를 실제 commit·rollback |
| `W`: semantic/causal weight | truth, STI/LTI, TECAN, traversal, neural parameter가 분리돼 존재 | slow scalar semantic weight와 experimental eligibility receipt; operator-W는 target | role별 semantic compatibility `K`와 causal efficacy `θ`를 분리해 외부 outcome으로 학습 |
| `A`: activation field | ECAN/TECAN attention, Context Frame, PC recurrent state | query potential/readout은 구현; token-native recurrent activation은 target | sparse token event가 n-ary incidence를 통과해 실제 route를 바꾸는 mediation |
| `F`: function cell | executable MeTTa graph, cognitive module, neural Space | 다중 typed LLM function-cell runtime은 target | black-box LLM/tool cell의 typed input/output와 sealed eligibility |
| `Π`: permission/governance | truth/fuel/policy 분리, proposal gate, promotion/rollback | capability·receipt·fail-closed 계약 일부 구현 | learned update와 external action 모두 exact-object authorization |
| provenance/history | 매우 강하게 설계됨 | HSWM의 강점이며 실제 artifact 계약이 있음 | novelty가 아니라 상호 검증·호환 대상으로 취급 |
| integrated learning efficacy | staged programme와 falsifiable target | 새 neural core는 미구현; 기존 일부 실험은 부정 결과 포함 | 양쪽 모두에게 없는 공개 end-to-end causal evidence를 먼저 만들기 |

Hyperon이 현재 더 앞선 부분은 architecture 폭, reflective language, metagraph runtime
계보, predictive-coding component, distributed/governance 설계다. HSWM이 현재 능력으로
앞섰다고 말할 근거는 없다. HSWM의 잠재적 차이는 더 좁고 수치적인 `K/θ/W/H`
학습계약과 결과를 숨기지 않는 efficacy receipt에 있다.

현재 HSWM P1의 `outcome→eligibility→candidate ΔW→fresh/canary→CAS` engineering path는
구현됐지만 scientific result는 RED다. 12개 candidate 중 fresh pass와 activation은
각각 `0`, held-out top-10 order/membership 변화도 `0`이었다. 따라서 여기서 말하는
HSWM delta는 이미 이긴 capability가 아니라 다음 실험에서 반증 가능하게 만들 target이다.

## 12. Hyperon 때문에 폐기해야 할 HSWM 주장

다음 문구는 사용하지 않는다.

- “LLM과 persistent hypergraph를 처음 결합했다.”
- “token hidden state에서 graph를 read/write하는 최초 구조다.”
- “비파괴 provenance와 rollback을 cognition에 처음 넣었다.”
- “shared/private graph로 여러 AI를 하나로 만드는 최초 구상이다.”
- “attention economics와 graph weight를 처음 결합했다.”
- “causal ablation으로 learned cognitive structure를 승격하는 최초 설계다.”

대신 다음처럼 한정한다.

> HSWM은 role-bearing n-ary incidence의 semantic compatibility와 external-outcome causal
> efficacy를 명시적으로 분리해, LLM token event→function cell→world outcome→versioned
> `ΔW/ΔH`로 닫히는 폐루프를 공개 구현·검증하려는 연구 프로그램이다.

이 문장도 구현·실험 전에는 **가설**이지 달성 사실이 아니다.

## 13. 수입할 것과 보류할 것

### 13.1 바로 수입할 설계 원칙

1. claim마다 `IMPLEMENTED / PROTOTYPE / SPECIFIED / HYPOTHESIS / VALIDATED`를 붙인다.
2. truth, salience, causal utility, compute credit, permission을 서로 다른 typed ledger로 둔다.
3. neural write는 truth가 아니라 provenance-bearing candidate로 시작한다.
4. candidate→shadow→causal audit→scoped promotion→monitor→rollback을 공통 lifecycle로 둔다.
5. private/local space와 shared space 사이에 typed capability와 evidence closure를 둔다.
6. AtomSpace/MORK는 경쟁자이면서 backend 후보이므로 adapter benchmark로 평가한다.

### 13.2 아직 넣지 말 것

- SWM-0 인과 loop 전의 거대 PRIMUS/Omega 전체 모사;
- 효능 전의 TECAN 경제와 자기수정 생태계;
- 모든 state의 blockchain anchoring;
- full native QuantiMORK 같은 장기 substrate 통합;
- 설계 수식을 observed result처럼 인용하는 문서화.

## 14. Hyperon과 직접 결판할 최소 실험

동일 task, model, input/output token, retrieval result count, latency와 tool budget에서 다음
arm을 비교한다.

| arm | 내용 |
|---|---|
| `B0` | base LLM |
| `B1` | LLM + flat vector memory |
| `B2` | LLM + read-only AtomSpace/metagraph retrieval |
| `B3` | Hyperon-style symbolic candidate read/write, outcome learning 없음 |
| `H0` | HSWM topology와 operator 고정 |
| `H1` | HSWM `θ_fast` external-outcome learning |
| `H2` | `H1`의 learned operator shuffle |
| `H3` | `H1`의 learned epoch rollback |

필수 판정은 다음과 같다.

1. `H1 > H0`가 held-out external outcome에서 재현되는가?
2. learned incidence/operator를 제거·shuffle하면 이득이 사라지는가?
3. pre-outcome eligibility가 없는 관계는 credit을 받지 않는가?
4. `ΔW`가 다음 token route/action 확률을 예측 가능한 방향으로 바꾸는가?
5. rollback이 transcript가 아니라 numeric state mediation을 제거하는가?
6. false write, calibration, latency, memory, energy를 포함해 matched budget에서도 이기는가?
7. role-aware n-ary operator가 degree-matched pairwise/clique baseline을 이기는가?

이 중 하나라도 빠지면 “Hyperon보다 구현이 구체적이다”는 말은 가능해도
“Hyperon보다 학습 구조가 작동한다”는 말은 할 수 없다.

## 15. 최종 경계

Hyperon은 HSWM을 무효화하지 않는다. 대신 HSWM의 중심을 정확하게 좁힌다.

```text
Hyperon이 이미 강하게 선행한 것
  persistent metagraph + reflective program + LLM bridge
  + attention economics + provenance/promotion/rollback
  + private/shared cognition

HSWM이 아직 증명해야 할 것
  LLMTokenEvent
    → role-bearing persistent n-ary activation
    → explicit semantic compatibility K
    → separately measured causal efficacy θ
    → typed LLM/tool function cell
    → external outcome receipt
    → eligibility-bound ΔW
    → governed ΔH
    → changed next-token/action behavior
```

가장 정확한 한 문장은 다음이다.

> **Hyperon 2026은 HSWM의 가장 강한 아키텍처 선행이자 잠재적 부품 공급원이다.
> HSWM의 독자성은 더 큰 세계관이 아니라, Hyperon이 아직 staged research programme으로
> 남겨 둔 폐루프를 더 명시적인 weight semantics와 재현 가능한 외부-outcome 실험으로
> 실제 구현할 때만 성립한다.**

## 16. 1차 자료

- [Hyperon Deep-Dive Whitepaper, July 2026](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf)
- [trueagi-io/hyperon-experimental](https://github.com/trueagi-io/hyperon-experimental)
- [hyperon-experimental v0.2.10](https://github.com/trueagi-io/hyperon-experimental/releases/tag/v0.2.10)
- [trueagi-io/MORK](https://github.com/trueagi-io/MORK)
- [trueagi-io/FabricPC](https://github.com/trueagi-io/FabricPC)
- [trueagi-io/pln-experimental](https://github.com/trueagi-io/pln-experimental)
- [singnet/DAS](https://github.com/singnet/das)
- [asi-alliance/OmegaClaw-Core](https://github.com/asi-alliance/OmegaClaw-Core)
- [OpenCog AtomSpace](https://github.com/opencog/atomspace)
- [OpenCog Classic ECAN implementation](https://github.com/opencog/attention)
- [OpenCog ECAN status](https://wiki.opencog.org/w/OpenCogPrime%3AEconomicAttentionAllocation)
