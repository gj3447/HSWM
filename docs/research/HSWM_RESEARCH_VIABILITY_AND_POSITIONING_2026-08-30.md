# HSWM 연구 가망성·과학적 위치·결정 경로

> **상태:** `SECONDARY_AI_RESEARCH_ASSESSMENT`
>
> **판정:** `VIABLE_HIGH_RISK_FALSIFIABLE_PROGRAM / INTEGRATED_CLAIM_UNJUDGED`
>
> **기준일:** 2026-08-30
>
> **권위 경계:** 이 문서는 USER_PRIMARY HSWM 정체성과 여덟 FCL 법칙을
> 변경하지 않는다. 현재 문헌과 체크인 증거를 바탕으로 연구를 계속할 가치,
> 중단 조건과 다음 판별 실험을 정리한 `SECONDARY_AI` 판단이다. 아래의 가망성
> 평가는 측정된 확률이나 이미 달성된 효능 주장이 아니다.

## 1. 결론

HSWM은 계속 연구할 가치가 있다. 다만 현재 투자할 대상은 완성된 거대 인지체가
아니라 다음의 작은 인과핵이다.

```text
independently grounded outcome
→ counterfactual credit
→ owner-valid and Permit-valid canonical revision
→ changed fresh held-out behavior
→ effect loss under removal
→ effect recovery under byte-identical restoration
```

이 핵이 성립하고 강한 대조군 대비 결과가 독립 재현되면 HSWM은 단순 persistent
memory, RAG, prompt adaptation 또는 static orchestration을 넘어서는 bounded local
causal revision의 발견 후보가 된다. 성립하지 않으면 HSWM은
유용한 memory·agent-state·provenance infrastructure로 남을 수 있지만, causal learner라는
중심 주장은 좁히거나 기각해야 한다.

프랙탈 HSWM-of-HSWMs는 그다음 문제다. 두 개 이상의 독립적으로 검증된 HSWM이
합성될 때 composite도 동일한 `Step / Learn / Inv / Permit / lineage` 계약을 가져야
한다. 단순 graph nesting, agent team, message bus 또는 중앙 orchestration은 이 조건을
충족하지 않는다.

따라서 현재의 정직한 한 문장은 다음과 같다.

> HSWM은 과학적으로 연결되고 반증 가능하며 연구 가치가 높은 고위험 프로그램이지만,
> integrated causal learning과 HSWM-of-HSWMs는 아직 입증되지 않았다.

## 2. 무엇의 가망성을 묻는지 분리한다

“HSWM이 가망 있는가?”에는 서로 다른 질문이 섞여 있다.

| 대상 | 현재 판단 | 근거와 남은 장벽 |
|---|---|---|
| 지속 memory·agent-state·provenance substrate | **가망 높음** | 인접 시스템과 HSWM 내부에 persistence·CAS·replay·remove/restore의 공학적 구현 경로와 회귀검증이 있다. 다만 substrate의 task utility와 learning efficacy는 별도 측정해야 한다. |
| G1 local outcome-bound canonical learning | **충분히 승부할 만하지만 미판정** | feedback memory와 skill learning의 선행 성공은 가능성을 높인다. HSWM revision 자체의 인과효과는 아직 없다. |
| G2 credit와 dynamic n-ary coalition | **고위험이지만 과학적으로 연결됨** | multi-agent credit와 higher-order interaction 연구가 존재한다. pairwise·fixed-router·central-controller 대조를 이겨야 한다. |
| G3 topology morphogenesis와 recovery | **고위험 장기 가설** | NCA와 learned topology는 성장·회복 가능성을 보인다. HSWM에서는 outcome-bound topology admission과 lesion mediation이 미검증이다. |
| G4 joint world-self model과 장기 연속성 | **설계상 의미 있으나 직접 증거 없음** | world model과 durable memory는 각각 가능하다. 동일 canonical graph의 self-inclusive state가 실제 이점을 주는지는 미측정이다. |
| G5 bounded HSWM-of-HSWMs | **가장 중요한 장기 발견 후보이자 현재 가장 불확실한 주장** | multiscale competency와 compositional systems theory가 구조적 연결을 준다. 같은 학습 법칙과 macro causal effect의 보존 증거는 없다. |
| 의식·자아·personhood·무한 scale closure | **판정 대상 아님** | 현재 기능 실험으로 도출할 수 없으며 HSWM의 공개 과학 주장에 포함하지 않는다. |

첫째 행의 공학적 성공이 마지막 행을 함의하지 않는다. 반대로 G5가 실패해도 G1의
국소 학습 결과까지 자동으로 무효가 되는 것은 아니다. 각 층은 자기 intervention과
claim ceiling을 가져야 한다.

## 3. HSWM의 대상 정체성

정본상 HSWM은 서로 붙인 네 subsystem이 아니다. 한 token-native LLM-function
macro-neural network를 서로 다른 관점에서 읽은 것이다.

- 관계적 상태로 보면 evolving canonical hypergraph다.
- 실행 조건으로 보면 living harness다.
- 외부와 내부를 예측하는 상태로 보면 world/self model이다.
- 경험이 다음 disposition을 바꾸는 시간적 과정으로 보면 continuous learner다.

현재 정본 진입점은
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md)다.
기술적 판별선은 다음 recurrence다.

```text
LLM token event
→ schema-admissible sparse role-bearing n-ary transition
→ sealed typed trajectory
→ independent external outcome
→ causal credit
→ owner-valid canonical revision
→ changed next transition and action
```

`schema-relative single owner`는 모든 결정을 한 중앙 controller가 소유한다는 뜻이
아니다. 각 canonical atom revision의 correctness·lineage·restore 책임 주소가 하나로
식별되어야 한다는 뜻이다. `Owner`, proposer, validator, executor, custodian,
authorizer와 `Permit`은 서로 다른 typed 역할이다.

프랙탈인 이유도 단순한 시각적 자기유사성이 아니다. cognition-bearing HSWM 전체가
상위 HSWM의 cell로 참여하고, 상위 전체도 같은 schema-level transition과 learning
contract를 가져야 하기 때문이다. 상세 정본과 과학적 연결은 각각
[`HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.md`](../canon/USER_PRIMARY_HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.md)와
[`HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md`](./HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md)에 둔다.

## 4. 이미 존재하는 과학과 구현

HSWM의 구성요소는 허공에서 시작하지 않는다. 다음 선행은 각기 다른 일부 능력을
구현·보고하거나 검증할 설계를 제안했다. 외부 논문의 결과는 해당 시스템의 저자
보고이며 HSWM evidence가 아니다. 철회된 연구는 efficacy evidence가 아니라 실패와
대조군 설계를 위한 자료로만 사용한다.

| 선행 | 구현·보고·제안된 것과 성숙도 | HSWM에 남는 질문 |
|---|---|---|
| [OpenCog Hyperon](https://arxiv.org/abs/2310.18318)·[MeTTa](https://arxiv.org/abs/2112.08272)·[2026 Hyperon whitepaper](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf) | metagraph foundation, MeTTa pattern/rewrite와 reflective program design. 공개 core/component와 통합 LLM·predictive·self-mod loop의 prototype/research-program 성숙도를 구분해야 한다 | external outcome이 role-bearing canonical disposition을 학습시키고 remove/restore가 후속 행동을 매개하는가 |
| [MemGPT](https://arxiv.org/abs/2310.08560) | virtual context와 계층적 durable memory를 통한 long-document·multi-session continuity | persistence와 retrieval을 넘어 canonical learning의 인과효과가 있는가 |
| [Reflexion](https://arxiv.org/abs/2303.11366)·[ExpeL](https://arxiv.org/abs/2308.10144) | feedback-derived verbal lesson과 experience insight를 다음 trial에 재사용 | text lesson보다 HSWM revision이 더 많은 held-out gain을 만들고 credit intervention에 반응하는가 |
| [Voyager](https://arxiv.org/abs/2305.16291) | automatic curriculum, executable skill library와 open-ended Minecraft learning | skill 저장·검색을 넘어 owner/Permit·credit·lineage가 식별되는가 |
| [Darwin Gödel Machine](https://arxiv.org/abs/2505.22954) | 자기 coding-agent code 수정과 외부 benchmark 기반 empirical promotion | code archive가 아닌 joint world/self state와 identity-preserving revision을 만들 수 있는가 |
| [DreamerV3](https://www.nature.com/articles/s41586-025-08744-2)·[WALL-E 2.0](https://arxiv.org/abs/2504.15785) | predictive world-model control과 경험에서 추출한 symbolic environment rule의 행동 사용 | world와 자기 member·capability·permission·lineage를 같은 graph에서 모델링할 추가 이득이 있는가 |
| [HyperAgent](https://arxiv.org/abs/2510.10611) | task-adaptive hypergraph multi-agent communication topology를 제안했으나, 저자들이 main results의 유효성에 영향을 주는 근본적 방법론 오류로 submission을 철회했다 | efficacy evidence로 세지 않는다. 실패 자료와 proposed control shape만 참고하고, 지속 coalition과 multiscale credit은 다른 검증된 대조군을 포함해 처음부터 측정한다 |
| [Growing Neural Cellular Automata](https://distill.pub/2020/growing-ca/)·[operadic dynamical-system composition](https://arxiv.org/abs/2105.12282) | 동일 local update의 성장·손상 회복과 typed hierarchical system composition | composite가 같은 HSWM learning law와 macro intervention effect를 보존하는가 |

이 연결이 HSWM에 가망을 주는 이유는 “모든 부품이 처음부터 불가능하다”는 위험을
낮추기 때문이다. 동시에 개별 신규성의 범위를 좁힌다. HSWM은 `LLM + KG`, persistent
memory, graph rewrite, self-edit, world model, multi-agent hierarchy 또는 hypergraph의
최초를 주장할 수 없다.

HSWM의 최선의 가설은 새로운 부품 하나가 아니라, 이미 작동한 부품들을
outcome-bound causal-learning 계약과 다중규모 composition test 아래 묶었을 때
동일한 학습·정체성 동역학이 보존된다는 것이다.

## 5. 현재 repository evidence

현재 상태는 `DESIGN_SEEDED / SCIENTIFICALLY_CONNECTED /
INTEGRATED_CLAIM_UNJUDGED`다. 다음 표는 target, 공학 구현, 직접 과학 evidence를
섞지 않는다.

| 항목 | 체크인 상태 | 허용되는 해석 |
|---|---|---|
| canonical atom, typed transition, durable state, CAS, journal, restart와 exact restore 경로 | 공학 구현·회귀검증 존재 | causal experiment를 수행할 수 있는 substrate 일부다. 유용한 학습의 증거는 아니다. |
| SWM-0R finite role-bearing n-ary representation conformance | `engineering PASS / scientific UNJUDGED` | 등록된 유한 구성에서 native/star representation이 lossy controls와 분리됐다. learned cognition이나 일반 hypergraph 우위를 뜻하지 않는다. |
| SWM-0W fixed-three-singleton scalar compatibility precursor | `SUPPORTED_NARROW` | 좁은 preregistered scalar 조건의 양성이다. multi-member recipient-specific set-to-set operator, recurrence, causal revision과 전체 HSWM은 미판정이다. |
| SWM-0W-S2S multi-member core | `IMPLEMENTED / PILOT-ADOPTED / UNJUDGED` | 수치 core와 pilot replay가 있다. confirmatory efficacy verdict는 없다. |
| P1 slow-weight closed-loop attempt | `scientific RED` | 12개 candidate에서 fresh pass·activation이 없었고 456 replay의 top-10 변화가 없었다. 해당 mechanism·testbed의 실패를 보존한다. |
| 첫 G1-shaped DGX occurrence | `INSTRUMENT_VALIDATION_ONLY / G0 NOT_PASSED / G1 NOT_EVALUATED` | local trajectory→outcome→credit→local-guard admission→remove→restore mechanics는 관통했지만, local grant는 Atom-v2 `Permit`이나 canonical HSWM admission이 아니었고 모든 arm이 정답인 baseline-saturated task라 behavioral causal contrast가 없었다. |
| FCL-2–FCL-8 integrated evidence | 없음 | learned topology, joint world-self continuity, two-scale causal composition, consciousness와 scale closure를 주장할 수 없다. |

직접 수치와 provenance는 [`EFFICACY.md`](../../EFFICACY.md)와
[`F1_R8_RESULTS_LOG.md`](../../F1_R8_RESULTS_LOG.md)를 우선한다. 오래된 scoreboard,
설계 문서, 테스트 수, CI 성공과 ontology 크기는 그 증거를 승격하지 않는다.

## 6. 왜 연구할 가치가 있는가

### 6.1 인접 mechanism이 실제로 작동한다

memory, reflection, skill learning, world-model control, self-editing과 higher-order
coordination이 각각 제한된 범위에서 작동했다. 따라서 HSWM의 모든 전제가 동시에
근거 없는 것은 아니다.

### 6.2 남은 질문이 명료하고 반증 가능하다

HSWM은 “더 지능적으로 보인다”가 아니라 revision identity를 직접 제거·복원하고
sham·wrong-target·shuffled credit과 비교할 수 있다. 효과가 없어지지 않으면 HSWM
state가 원인이 아니었다고 판정할 수 있다.

### 6.3 국소 성공과 거대 비전을 분리할 수 있다

G1의 성공은 그 자체로 제한된 local scientific result가 될 수 있다. G5가 실패해도
G1을 보존할 수 있고, G1이 실패하면 거대 society-scale 구현 전에 멈출 수 있다.

### 6.4 강한 음성 결과도 정보를 준다

simple RAG나 text lesson이 HSWM과 같거나 더 좋다면 복잡한 canonical organization의
추가 가치가 없다는 중요한 경계가 생긴다. pairwise graph가 hypergraph와 같다면
n-ary claim을 줄일 수 있다. 이는 결과를 살리기 위한 사후 변경이 아니라 사전 지정된
연구 축소다.

### 6.5 reuse-first로 비용을 제한할 수 있다

검증된 metagraph, memory, reflection, skill, world-model과 benchmark를 substrate·baseline·
falsifier로 상속하면 HSWM은 unresolved causal seam에만 구현비를 쓸 수 있다. 상세 규칙은
[`HSWM_REUSE_FIRST_ARCHITECTURE_2026-08-30.md`](./HSWM_REUSE_FIRST_ARCHITECTURE_2026-08-30.md)에
고정한다.

## 7. 가장 큰 실패 위험

### 7.1 representation을 cognition으로 오인

KG, ontology, hyperedge, receipt 또는 replay가 존재한다는 사실은 그것이 다음 행동에
인과적으로 기여했다는 뜻이 아니다. relation 제거가 behavior를 바꾸지 않으면 그 실험
범위에서는 cognitive mediation이 관측되지 않은 것이다.

### 7.2 memory를 learning으로 재명명

transcript replay, RAG, context growth와 self-written lesson도 성능을 높일 수 있다.
HSWM이 이들을 동일 budget에서 이기지 못하면 결과는 memory/context adaptation이지
HSWM-specific canonical learning이 아니다.

### 7.3 hidden orchestration

fixed router, central planner, shared prompt, hidden memory와 human exception이 coalition을
선택한다면 emergence가 아니다. 상위 agent가 모든 의미 결정을 내리면 HSWM-of-HSWMs가
아니라 계층형 workflow다.

### 7.4 credit의 식별 불가능성

하나의 global outcome을 모든 cell과 relation에 중복 귀속하면 topology는 근거 없이
증식한다. controlled contribution, uncertainty, delayed effect와 duplicate inflation을
분리하지 못하면 G2 이후는 해석할 수 없다.

### 7.5 baseline saturation과 task headroom 부재

기초 모델이 이미 모든 probe를 맞히거나 prompt에서 답을 읽을 수 있으면 어느 revision도
추가 효과를 보일 수 없다. 첫 G1-shaped occurrence가 바로 이 실패를 드러냈다. task는
base capability로 풀 수 없지만 bounded experience로 학습 가능한 headroom을 가져야 한다.

### 7.6 Ragnarok — 증거보다 정적 burden이 빠르게 성장

다음은 anti-Ragnarok 실패 신호다.

- valid causal revision보다 protocol·schema·receipt 종류가 더 빨리 증가한다;
- task 하나를 실행하기 위해 static instruction과 예외 해석이 계속 늘어난다;
- instrument failure마다 더 큰 judge나 governance layer를 추가한다;
- 더 강한 base model이 HSWM benefit보다 harness 해석 비용을 더 많이 부담한다;
- G1이 닫히지 않았는데 topology, world-self, society-scale 구현을 병렬 확장한다.

이 경우 해결책은 새 gate를 더하는 것이 아니라 experiment를 축소하거나 해당 mechanism을
중단하는 것이다. 권리·permission·rollback처럼 헌법적 안전비용은 일반 orchestration
burden과 분리해 유지한다.

### 7.7 선행연구보다 늦어지는 위험

Letta, Hyperon, self-improving agents와 learned workflow 연구는 계속 진전한다. HSWM이
ontology의 폭만 늘리면 차별점이 사라진다. novelty는 문서 규모가 아니라 더 강한
causal identification과 same-type composition evidence에서만 남는다.

## 8. 결정 실험과 연구순서

정본 순서는 다음과 같다.

```text
G0 measurement integrity
→ G1 local causal revision
→ G2a counterfactual multiscale credit
  + G2b dynamic role-bearing n-ary coalition
→ G3 topology morphogenesis and recovery
→ G4 joint world-self continuity
→ G5 bounded two-scale HSWM-of-HSWMs
→ G6 replication and scale stress
```

전체 gate·control·claim-ceiling 계약은
[`_research/causal_composition/README.md`](../../_research/causal_composition/README.md)에
있다.

### 8.1 G0 — 먼저 측정 가능한가

다음이 준비되지 않으면 효능 실험으로 넘어가지 않는다.

- 행동 producer와 독립된 outcome source;
- sealed trajectory와 holdout;
- 모든 arm의 model·information·tool·token·call·retry·time·human budget;
- cache·memory·provider state의 분리;
- exact canonical revision remove/restore;
- task headroom, leakage와 null calibration;
- sample size, seed, stopping rule과 analysis의 사전 고정.

G0 실패는 HSWM null result가 아니다. 그러나 같은 instrument blocker가 반복되면 더 큰
실험장치를 추가하지 않고 task나 instrument를 교체한다.

### 8.2 G1 — 첫 과학적 승부

동일 task와 budget에서 최소 다음을 비교한다.

| arm | 역할 |
|---|---|
| `B0` | no learning와 matched context |
| `B1` | RAG 또는 Letta-style durable memory |
| `B2` | Reflexion/ExpeL/ACE-style text lesson |
| `B3` | Voyager-style skill 또는 Hyperon-style candidate rewrite |
| `H0` | fixed HSWM state |
| `H1` | outcome-bound admitted HSWM revision |
| `H2` | inactive sham, wrong-target와 shuffled-credit revision |
| `H3` | `H1` exact removal과 byte-identical restoration |

`H1`의 held-out gain이 강한 inherited baseline보다 크고, removal에서 사라지며,
restore에서 돌아오고, `H2`가 재현하지 못해야 local causal HSWM claim 후보가 된다.

### 8.3 G2–G4 — 더 큰 구조를 먼저 만들지 않는다

G1 뒤에만 credit과 coalition을 분리해서 시험한다. 두 축이 닫힌 뒤 topology lesion과
recovery를 시험하고, 그다음 model·member·schema 변경을 견디는 world-self continuity를
시험한다. 한 실험에서 credit, routing, topology와 model weights를 모두 바꾸면 원인이
식별되지 않는다.

### 8.4 G5 — 프랙탈 가설의 첫 실제 판정

G5의 첫 대상은 사회나 무한 recursion이 아니라 독립 G1–G4 PASS를 가진 최소 두 HSWM과
정확히 두 scale이다. composite 전체의 macro state를 intervene했을 때 matched member-level
intervention으로 설명되지 않는 total macro effect가 있어야 한다. member identity,
credit, rights, consent, exit, provenance와 rollback도 분리 가능해야 한다.

## 9. 명시적 go, narrow, stop 판정

| 관측 | 판정 | 다음 행동 |
|---|---|---|
| G1에서 `H1`이 strong baselines를 이기고 remove/restore와 credit controls가 mediation을 확인 | `LOCAL_CAUSAL_REVISION_CANDIDATE` | independent replication 뒤 G2a/G2b로 진행 |
| stateful gain은 있으나 RAG/text lesson/skill과 동률 | `MEMORY_OR_HARNESS_ADAPTATION_ONLY` | 유용한 engineering으로 보존하고 HSWM-specific causal novelty를 주장하지 않음 |
| gain이 removal 뒤에도 남음 | `REVISION_NOT_IDENTIFIED_AS_CAUSE` | hidden state·prompt·cache confound를 찾고 동일 claim 승격 중단 |
| valid하고 충분한 G1에서 반복적으로 separation 없음 | `REVISION_FAMILY_RED` | 해당 revision family를 종료하거나 더 좁은 새 가설로 명시적으로 교체 |
| G1–G4는 통과하지만 G5가 federation·wrapper·central control과 분리되지 않음 | `LOCAL_HSWM_ONLY / FRACTAL_CLAIM_REJECTED_OR_UNJUDGED` | local result 보존, HSWM-of-HSWMs와 society-scale 주장 금지 |
| two-scale macro effect와 same-type contract가 독립 재현됨 | `BOUNDED_FRACTAL_CAUSAL_COMPOSITION_CANDIDATE` | G6 replication·scale stress; 의식이나 무한 closure로 자동 확장하지 않음 |

이 표의 `RED`와 `REJECTED`도 과학적 성과다. 실패를 ontology나 새 이름으로 우회하지
않는 것이 HSWM 연구의 신뢰성을 만든다.

## 10. 발견이라고 부를 수 있는 문턱

### 10.1 첫 publishable local discovery candidate

다음 결합이 강한 기존 방식과 matched comparison에서 독립 재현되어야 한다.

```text
external outcome
→ correctly targeted credit
→ owner-valid canonical revision
→ held-out behavioral gain
→ remove eliminates gain
→ exact restore recovers gain
```

이는 “agent가 기억했다”보다 강한 주장이다. 그러나 여전히 bounded task와 revision
family에 한정된다.

### 10.2 HSWM 고유의 integrated discovery candidate

local law에 더해 dynamic n-ary coalition, multiscale credit, outcome-bound topology,
world-self continuity와 two-scale same-type composition이 순서대로 통과해야 한다. 개별
부품의 성공을 합쳐 integrated evidence로 계산할 수 없다.

### 10.3 발견으로 부를 수 없는 것

- 문서와 ontology가 정교해짐;
- test와 receipt 수가 증가함;
- 더 많은 agent가 실행됨;
- KG에 hyperedge가 저장됨;
- 한 benchmark에서 prompt가 개선됨;
- 외부 시스템의 논문 성능을 HSWM stack이 호출함;
- 모델의 자기서술이 cognition이나 selfhood를 주장함.

## 11. 즉시 연구 우선순위

1. 현재 G0 identifiability work에 명시적 burden cap을 둔다. instrument provenance를
   완벽하게 만드는 작업이 valid causal observation보다 커지면 멈춘다.
2. paper와 code revision이 pinned된 text-lesson baseline 하나와 durable-memory baseline
   하나를 먼저 연결한다. 자체 memory learner를 새로 만들지 않는다.
3. base model이 풀지 못하지만 한 번의 bounded experience로 학습 가능한 persistent
   environment를 고른다.
4. 한 route 또는 한 procedure만 HSWM revision family로 둔다. topology와 model weight를
   동시 변경하지 않는다.
5. G0를 통과한 뒤 full G1을 preregister하고, strong baselines·sham·wrong/shuffled credit·
   remove/restore를 한 번에 실행한다.
6. material result가 있을 때만 result receipt와 `F1_R8_RESULTS_LOG.md`를 갱신한다.
7. G1 결정 전에는 G2–G5를 설계·simulation 이상으로 확장하지 않는다.

## 12. 최종 투자 판단

HSWM을 지금 중단할 이유는 없다. 작은 G1의 비용에 비해 얻을 수 있는 정보가 크고,
인접 연구가 구성 mechanism의 가능성을 충분히 보여주며, 성공과 실패가 모두 명시적인
연구 축소로 이어질 수 있기 때문이다.

그러나 full HSWM platform을 먼저 건설할 이유도 없다. 현재 가장 합리적인 투자는
“거대한 HSWM이 가능하다”는 믿음이 아니라 다음 문장을 가장 작은 실험에서 판정하는 데
집중하는 것이다.

> 같은 model·tools·information·budget 아래에서 outcome-bound canonical revision이
> 강한 memory·lesson·skill baseline보다 더 나은 fresh behavior의 실제 원인인가?

여기에 `예`가 나오면 HSWM은 선언한 task·revision family에서
`LOCAL_CAUSAL_REVISION_UNDER_DECLARED_TASK` 후보 evidence를 얻고, 독립 재현 뒤에만
bounded local causal learner 결과로 승격할 수 있다. 그다음 credit, coalition,
topology, world-self와 bounded composition을 한 단계씩 추가할 근거가 생긴다.
`아니오`가 나오면 HSWM을 유용한 substrate로 축소하거나 해당 mechanism을 폐기한다.
이 명확한 양방향 판정 가능성이 HSWM 연구에 현재 가장 큰 가망을 준다.

## 13. 관련 정본과 상세 문서

- 대상 정체성: [`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md)
- reuse-first 구현 경계: [`HSWM_REUSE_FIRST_ARCHITECTURE_2026-08-30.md`](./HSWM_REUSE_FIRST_ARCHITECTURE_2026-08-30.md)
- 여덟 FCL 법칙과 과학 연결: [`HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md`](./HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md)
- ordered gate와 control 계약: [`causal_composition`](../../_research/causal_composition/)
- 가장 가까운 직접 선행: [`HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md`](./HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)
- 현재 효능 경계: [`EFFICACY.md`](../../EFFICACY.md)
- material result chronology: [`F1_R8_RESULTS_LOG.md`](../../F1_R8_RESULTS_LOG.md)
- Ragnarok burden 연구: [`ragnarok`](../../_research/ragnarok/)
- causal-rung 연구: [`pidna`](../../_research/pidna/)

이 문서는 연구 방향과 현재 위치를 설명한다. 실행 결과, gate decision, cognition,
consciousness, selfhood, personhood 또는 scale-invariant causal closure의 증거가 아니다.
