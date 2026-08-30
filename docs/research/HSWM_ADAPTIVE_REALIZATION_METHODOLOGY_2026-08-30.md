# HSWM adaptive realization methodology

> **상태:** `SECONDARY_AI_RESEARCH_METHODOLOGY`
>
> **과학적 상태:** `SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`
>
> **USER_PRIMARY 방향:**
> [`HSWM Adaptive Research Strategy`](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)
>
> **역할:** 최종 HSWM target을 유지하면서 algorithm·method·testbed·runtime 경로를
> 증거에 따라 교체하는 재현 가능한 연구 절차를 정의한다.

## 1. 결정

HSWM 연구는 하나의 구현 stack을 완성하는 프로젝트가 아니라, 고정된 target identity에
도달할 때까지 **실패한 realization path를 계보적으로 교체하는 탐색 프로그램**으로 운영한다.

```text
target identity와 FCL obligation        stable
scientific success criterion            stable or stronger
algorithm·method·backend·testbed         revisable
negative evidence와 decision lineage     append-only
public claim                             current evidence ceiling 이하
```

이때 `stable`은 경험적으로 참이라고 가정한다는 뜻이 아니다. target을 동일한 대상으로 계속
추적한다는 뜻이다. target의 각 경험적 bridge는 계속 반증 가능하고 현재 통합 상태는
`UNJUDGED`다.

## 2. 분리해야 할 ontology atom

| atom | 질문 | 최소 속성 |
|---|---|---|
| `ResearchCommitment` | 무엇을 끝까지 만들려는가 | source digest, target refs, nonclaim, status |
| `TargetInvariant` | 경로가 바뀌어도 어떤 대상 동일성을 보존하는가 | invariant ID, authority, FCL refs, amendment boundary |
| `AuxiliaryHypothesis` | 지금 시험하는 구체 mechanism은 무엇인가 | family, scope, predecessor, conceptual delta, status |
| `FalsificationContract` | 결과를 보기 전에 무엇으로 판정하는가 | intervention, nulls, baselines, budget, metric, threshold, stopping rule, claim ceiling, digest |
| `EvidenceEnvelope` | 실제로 무엇이 관측됐는가 | trajectory·outcome·code·model·config digest, all-arm results, exclusions, uncertainty |
| `MechanismDisposition` | 그 경로의 현재 지위는 무엇인가 | supported/red/underdetermined, scope, evidence UID, reviewer |
| `RerouteDecision` | 왜 무엇을 버리고 무엇으로 우회하는가 | failed auxiliary, preserved invariant, successor, unchanged controls, rationale |
| `ClaimCeiling` | 지금 공개적으로 어디까지 말할 수 있는가 | bounded claim, forbidden claims, replication requirement |

이 atom들은 한 문서의 중첩 필드로만 숨기지 않는다. 실패 경로, 새 경로, 판정과 근거를
각각 주소화해야 나중에 algorithm 계보와 반복 실패를 비교할 수 있다.

## 3. 상태기계

### 3.1 Auxiliary hypothesis

```text
DRAFT
→ PREREGISTERED
→ TESTING
→ SUPPORTED_WITHIN_SCOPE
 | RED_WITHIN_SCOPE
 | UNDERDETERMINED

RED_WITHIN_SCOPE
→ RETIRED_WITH_EVIDENCE_PRESERVED
→ REROUTE_PROPOSED
→ successor PREREGISTERED
```

`SUPPORTED_WITHIN_SCOPE`도 최종 상태가 아니다. 독립 재현, 범위 확장과 다른 FCL gate에는
각각 새 contract가 필요하다. `UNDERDETERMINED`는 음성 결과가 아니며 측정이나 task 경로를
수정한 뒤 다시 시작한다.

### 3.2 Falsification contract

```text
DRAFT → SEALED → EXECUTING → ANALYZED → ARCHIVED
```

`SEALED` 뒤에는 outcome을 보면서 contract를 수정하지 않는다. 실행 전에 결함을 발견하면
기존 bytes와 이유를 남기고 `SUPERSEDED_BEFORE_EXECUTION`으로 닫은 뒤 successor contract를
만든다. 실행 뒤 변경은 새 실험이다.

### 3.3 Integrated claim

```text
UNJUDGED
→ CANDIDATE_WITHIN_SCOPE
→ INDEPENDENTLY_REPLICATED_BOUNDED
```

서로 다른 부품의 개별 성공을 합산해 integrated HSWM을 만들지 않는다. local learning,
coalition, credit, topology, world-self와 two-scale composition 결합은 전용 통합 contract를
통과해야 한다.

## 4. reroute transaction

한 reroute decision은 최소 다음 질문에 답해야 한다.

1. 어느 exact hypothesis와 contract가 어떤 evidence 때문에 실패했는가?
2. 실패는 mechanism, testbed, instrument, estimator 또는 resource regime 중 어디에
   국한되는가?
3. 어떤 target invariant와 FCL obligation은 그대로 남는가?
4. successor mechanism의 conceptual delta는 무엇이며 왜 같은 실패를 피할 것으로
   예상하는가?
5. 기존보다 약해지지 않은 null, baseline, budget, intervention과 claim ceiling은 무엇인가?
6. 이전 실패를 재현하거나 구분할 diagnostic arm은 무엇인가?
7. 새 경로를 언제 `RED`, `UNDERDETERMINED`, `SUPPORTED_WITHIN_SCOPE`로 판정하는가?

이를 간단한 결정 절차로 쓰면 다음과 같다.

```text
if instrument_or_task_invalid:
    preserve run as UNDERDETERMINED
    replace instrument or testbed
elif declared_mechanism_fails_valid_controls:
    mark exact mechanism RED_WITHIN_SCOPE
    preserve all evidence and claim ceiling
    propose a different causal mechanism
    preregister same-or-stronger controls
elif bounded_effect_passes:
    retain mechanism only within scope
    require removal/restoration and independent replication
else:
    keep claim UNJUDGED
```

## 5. mechanism portfolio

HSWM target은 하나지만 동시에 탐색할 수 있는 realization family는 여러 개다.

| family | 바꿀 수 있는 것 | 계속 요구되는 판별선 |
|---|---|---|
| outcome·credit | difference, causal, influence, delayed 또는 uncertainty-aware attribution | 독립 outcome, shuffled/wrong-target control, contribution sensitivity |
| revision·admission | symbolic rule, operator, route, procedure, parameter 또는 topology proposal | owner/Permit-valid canonical identity, compiled mediation, remove/restore |
| memory·experience | RAG, episodic memory, lesson, skill, model-neutral macro-state | matched information budget와 memory-only baseline 분리 |
| coalition | auction, learned routing, recurrent ignition, constraint solving 또는 local negotiation | fixed router·central commander·pairwise·role-shuffle 대조 |
| topology | add/remove, split/merge, prune/grow, evolutionary search 또는 local update | outcome binding, lesion mediation, stability와 damage recovery |
| world-self | latent, symbolic, hybrid, predictive 또는 event-sourced representation | world-only·external registry·forged lineage·model-swap 대조 |
| composition | wrapper, federation, typed open-system, macro-state 또는 alternative boundary 후보 | same-type contract, macro intervention, member identity·exit·rollback 보존 |
| runtime·model | LLM, tokenizer, graph engine, store, language와 deployment fabric | 동일 semantic contract, state isolation, provenance와 matched resource |
| method·testbed | task, simulator, evaluator, estimator, gate ordering과 replication design | headroom, leakage control, prospective contract와 evidence lineage |

portfolio는 여러 mechanism을 한 run에서 동시에 바꾸라는 뜻이 아니다. 한 실험은 주된
intervention family를 하나로 제한하고, 서로 다른 경로는 독립 arm 또는 successor lineage로
분리한다.

## 6. 기존 G0–G6와의 결합

현재 [`causal-composition`](../../_research/causal_composition/)은 활성 dependency spine이다.

```text
G0 measurement
→ G1 local causal revision
→ G2a credit + G2b coalition
→ G3 morphogenesis
→ G4 world-self continuity
→ G5 two-scale composition
→ G6 replication and scale stress
```

이 spine은 downstream 규모로 upstream 실패를 숨기지 못하게 한다. 그러나 각 gate 안의
algorithm, instrument와 testbed는 교체할 수 있다. 새로운 연구 순서가 기존 식별 문제를 더
잘 푼다면 source-bound successor program을 만들 수 있지만, 통과하지 않은 prerequisite를
생략했다는 이유만으로 claim ceiling을 올릴 수 없다.

## 7. 대표적인 우회 판정

### 7.1 baseline-saturated G1 task

모든 arm이 이미 정답이면 revision 효과를 측정하지 못했다. 이것은 HSWM null도 mechanism
성공도 아니다. run을 `UNDERDETERMINED_TASK_HEADROOM`으로 보존하고, base model은 풀지
못하지만 bounded experience로 학습 가능한 task로 교체한다.

### 7.2 shuffled credit가 실제 credit와 같은 경우

valid G0 아래 반복되면 해당 credit family는 `RED_WITHIN_SCOPE`다. topology나 agent 수를
늘려 구제하지 않는다. causal estimator, delayed attribution 또는 intervention granularity가
다른 successor를 새 contract로 시험한다.

### 7.3 pairwise가 native hyperedge와 같은 경우

그 task와 representation에서는 native n-ary increment를 주장하지 않는다. 기존 결과를
보존하고 진짜 higher-order dependency가 있는 task, role-incidence 표현 또는 interaction
operator로 우회한다. 새 task의 양성은 이전 task의 음성을 지우지 않는다.

### 7.4 G5가 wrapper와 분리되지 않는 경우

시험한 macro boundary와 composition algorithm은 `COMPOSITION_PATH_RED_WITHIN_SCOPE`다.
local G1–G4 결과는 보존하고 FCL-8은 `UNJUDGED`로 남긴다. alternative macro partition,
whole-state definition, credit boundary 또는 typed composition rule을 바꾸어 다시 시험한다.

## 8. anti-immunization과 anti-Ragnarok

목표 지속성이 실패를 무효화하면 연구 프로그램은 퇴행한다. 반대로 실패마다 새 schema,
judge와 예외를 늘리면 Ragnarok burden이 학습보다 빠르게 성장한다.

각 reroute는 다음 두 비율을 함께 기록해야 한다.

```text
causal learning yield / total research and runtime burden
new discriminating evidence / added static protocol complexity
```

실패 원인을 분리하지 못하는 추가 ontology나 governance는 우회가 아니다. 안전·권리·Permit·
rollback 비용은 ordinary orchestration burden과 따로 보존하되, 효능을 만들었다고 계산하지
않는다.

## 9. KG 관계와 비주장

machine projection은 다음 관계를 구분한다.

- USER source가 research commitment의 방향을 고정한다;
- adaptive program이 target invariant와 FCL을 `PRESERVES`한다;
- auxiliary mechanism은 target을 `REALIZES`하려는 후보이지 evidence가 아니다;
- falsification guard가 claim을 `CONSTRAINS`하고 route를 `TESTS`한다;
- RED disposition의 evidence를 `PRESERVES`하고, `REROUTE_PROPOSED`가
  `RETIRED_WITH_EVIDENCE_PRESERVED`를 `SUPERSEDES_AS_FOLLOWUP`한다;
- bundle과 KG publication은 HSWM을 실행하거나 달성을 강제하지 않는다는 뜻으로
  target을 `DOES_NOT_ENFORCE`한다.

전용 projection은
[`HSWM_ADAPTIVE_RESEARCH_STRATEGY_ONTOLOGY.v1.json`](../../ontology/identity/hswm_core/HSWM_ADAPTIVE_RESEARCH_STRATEGY_ONTOLOGY.v1.json)이다.
이 projection에 node와 relation이 존재해도 어떤 mechanism, FCL 또는 HSWM 전체가 통과한
것은 아니다.

## 10. 현재 실행 원칙

1. 최종 HSWM과 FCL-1부터 FCL-8까지를 north-star target으로 유지한다.
2. 현재 immediate path는 G0/G1 identifiability와 local causal revision이다.
3. 실패한 mechanism과 instrument를 exact scope로 `RED` 또는 `UNDERDETERMINED` 처리한다.
4. 모든 successor는 predecessor evidence, conceptual delta와 같은 수준 이상의 control을
   가진다.
5. 문서·ontology·CI가 아니라 fresh behavior와 intervention 결과만 claim을 승격한다.
6. bounded 성공을 다음 scale이나 의식·personhood·무한 closure로 자동 일반화하지 않는다.
7. 최종 target은 축소하지 않되, 거짓 양성 없이 도달할 수 있도록 연구 topology를 계속
   바꾼다.
