# HSWM reuse-first research architecture

> **Status:** `SECONDARY_AI_RESEARCH_DIRECTION / ADOPT_PRIORS_TEST_DELTA`
>
> **Scientific status:**
> `SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`
>
> **Canonical boundary:** This document changes the implementation and
> comparison strategy, not the USER_PRIMARY HSWM identity or the eight FCL laws.

## 1. Decision

HSWM will inherit demonstrated engineering capabilities and published learning
mechanisms wherever they can be pinned, observed, intervened on, and licensed.
It will not rebuild a metagraph database, long-term agent memory, textual
reflection loop, skill library, world-model benchmark, multi-agent communication
optimizer, or morphogenetic simulator merely to give those capabilities HSWM
names.

The rule is:

```text
inherit demonstrated capability
→ expose it through one matched adapter contract
→ retain it as substrate, baseline, or falsifier
→ implement only the unresolved HSWM causal delta
```

External results remain evidence for their reported systems. They do not become
HSWM evidence merely because HSWM calls their code.

## 2. Target identity, current evidence, and conceptual delta

| layer | statement |
|---|---|
| target identity | One token-native LLM-function macro-neural network whose evolving canonical hypergraph is simultaneously living harness, world/self model, and continuous learner; cognition-bearing HSWMs may compose under the same typed dynamics. |
| current evidence | Persistent memory, metagraph rewriting, reflection, skill acquisition, world-model planning, self-editing agents, dynamic hypergraph communication, and local-rule morphogenesis all have direct scientific or engineering precedents. HSWM has not yet demonstrated their integrated causal closure. |
| conceptual delta | Stop treating known component capabilities as implementation targets. Test whether an independently grounded outcome causes a credit-valid, owner/Permit-valid canonical revision whose removal and byte-identical restoration remove and restore fresh held-out behavior, and later whether the same law survives bounded HSWM composition. |

The novelty budget is therefore deliberately narrow:

```text
independent outcome
→ counterfactual credit
→ owner-valid typed canonical revision
→ compiled behavioral disposition
→ fresh held-out behavior
→ exact removal and restoration
```

At composition scale, the additional unresolved claim is preservation of
`Step / Learn / Inv / Permit / identity-learning lineage` in the composite.

## 3. Prior systems are assigned roles, not absorbed as one giant stack

| prior family | reusable capability, proposal, or warning | HSWM disposition | what HSWM must not infer |
|---|---|---|---|
| [OpenCog Hyperon](https://arxiv.org/abs/2310.18318), [MeTTa](https://arxiv.org/abs/2112.08272), AtomSpace/MORK | typed persistent metagraph, rewrite/query execution, reflective program representation, versioned graph machinery | `ADAPTER_BACKEND_AND_STRONG_BASELINE`; evaluate read-only query and candidate-rewrite modes behind a pinned adapter | A metagraph runtime is not outcome-bound HSWM learning or recursive causal closure |
| [MemGPT](https://arxiv.org/abs/2310.08560), Letta-style memory | durable, tiered, model-context-external agent memory | `MEMORY_BASELINE`; compare with equal model, context, tools, token and state budgets | persistence or retrieval is not learning |
| [Reflexion](https://arxiv.org/abs/2303.11366), [Voyager](https://arxiv.org/abs/2305.16291), [ExpeL](https://arxiv.org/abs/2308.10144)/ACE-style memory | feedback-derived textual lessons, executable skills, and later-task reuse | `UPDATE_POLICY_BASELINE`; use a pinned reproduction or adapter before inventing a new text-lesson learner. The first B2 candidate is the [source-pinned ExpeL boundary](../../_research/causal_composition/priors/expel_b2_text_lesson_v1/README.md). | later improvement alone does not identify canonical revision, owner, or credit |
| [Darwin Gödel Machine](https://arxiv.org/abs/2505.22954) | sandboxed self-edit proposals validated on external coding benchmarks | `SELF_MODIFICATION_BASELINE_AND_PROPOSER`; reuse bounded propose-test-promote patterns | code self-editing is not world/self unification or identity-preserving HSWM learning |
| [DreamerV3](https://www.nature.com/articles/s41586-025-08744-2), [WALL-E 2.0](https://arxiv.org/abs/2504.15785), ALFWorld-class environments | predictive world models, symbolic environment rules, and executable outcome benchmarks | `WORLD_MODEL_BASELINE_AND_EVALUATION_ENVIRONMENT`; reuse environments and outcome contracts before building a new world | environment prediction alone is not a joint canonical world/self model |
| [HyperAgent](https://arxiv.org/abs/2510.10611) | proposed task-adaptive hypergraph communication topology; the authors withdrew the submission because a fundamental methodological error affects the validity of its main results | `WITHDRAWN_METHOD_REFERENCE_ONLY`; use only as a failed-study and control-design reference, never as positive efficacy evidence | a withdrawn result or transient communication hyperedge is not evidence for persistent cognition-bearing coalition |
| [Growing Neural Cellular Automata](https://distill.pub/2020/growing-ca/) and operadic dynamical-system composition | repeated local rules, damage recovery, typed hierarchical composition | `G3_G5_REFERENCE_AND_TOY_BASELINE`; reuse their perturbation and composition tests | structural self-similarity is not HSWM-of-HSWMs cognition or subjecthood |

These assignments are not dependency commitments. A prior is installed only
when its arm is required, its paper and code revision are pinned, its license is
compatible, and its hidden state can be bounded. This avoids replacing wheel
reinvention with dependency accumulation.

## 4. Adopt, wrap, reimplement, or reject

Every imported capability receives exactly one disposition before use.

### 4.1 `ADOPT`

Adopt a component directly only when it is claim-noncritical and its behavior is
observable and reproducible: parsers, stores, deterministic solvers, container
runtimes, benchmark environments, and query engines are typical candidates.

Required conditions:

- paper and code revision or release are pinned;
- code, model, and data licenses are separately recorded;
- inputs, outputs, network access, cache state, and durable writes are observable;
- the component cannot authorize a canonical HSWM mutation;
- offline replay or a sealed equivalent is possible.

### 4.2 `WRAP`

Wrap an agent, retriever, memory manager, or hosted model when it is useful but
opaque or semantically different from HSWM. The wrapper may return an
observation, retrieval result, action proposal, lesson, skill, rewrite proposal,
or predicted outcome. It may not directly perform HSWM credit, admission,
permission, ownership, or lineage mutation.

The common boundary is:

```text
PriorAdapter.propose(sealed_episode, visible_state, budget)
  → Proposal + ExternalStateDigest + ResourceReceipt

HSWM.admit(proposal, independent_outcome, credit, owner, permit)
  → Rejected | CanonicalRevisionReceipt
```

### 4.3 `CLEAN_ROOM_REIMPLEMENT`

Reimplement only the narrow part that determines the HSWM claim itself or that
cannot be intervened on through the public component:

- outcome-to-credit binding;
- schema-relative responsibility owner and separate `Permit` decision;
- canonical revision identity and compiled-state derivation;
- exact remove/restore intervention;
- role-bearing hyperedge credit and topology mutation;
- composite HSWM boundary, lineage, consent, exit, and rollback.

This is not avoidable wheel reinvention. These are the variables whose causal
effect HSWM claims, so delegating them to an opaque dependency would make the
claim unidentifiable.

### 4.4 `REJECT_OR_QUARANTINE`

Reject an import from scientific runs when its license or data provenance is
unclear, hidden writes cannot be disabled, evaluator leakage cannot be bounded,
state cannot be reset, or a fixed central controller cannot be separated from
the claimed emergent behavior.

## 5. Minimal G1 stack

G1 needs a common experiment plane, not a new general cognitive platform.

```text
frozen task + LLM + tools + independent outcome adapter
    ├── B0  no learning / matched context
    ├── B1  RAG or Letta-style durable memory
    ├── B2  Reflexion/ExpeL/ACE-style textual lesson
    ├── B3  Voyager-style bounded skill or Hyperon-style candidate rewrite
    ├── H0  fixed HSWM state
    ├── H1  admitted outcome-bound HSWM revision
    ├── H2  sham, wrong-target, or shuffled-credit HSWM revision
    └── H3  H1 removal and byte-identical restoration

all arms
    → same fresh and retention tasks
    → same information, model, tool, token, call, retry, time, and human budget
    → one sealed result and resource schema
```

The checked-in [`pre_g1_screen`](../../src/hswm/experiments/pre_g1_screen.py)
is deliberately below this G1 comparison. It reuses the DNRD-5
custody-separated two-hypothesis task material to exercise separate-process
outcome/sham/score boundaries and a local immutable-store remove/restore
envelope. It is a source-checkout-only research adapter, not a packaged wheel
API. That task exposes the same one-bit rule to a structured local revision
and a text-shaped surrogate. It can test instrumentation and local store
mechanics, but it cannot establish an ExpeL replication, comparative HSWM
efficacy, G0 passage, or G1 passage. Backend context/cache isolation is only
adapter-reported in this local screen, not platform-verified, so H3 behavioral
scores are not removal evidence. The surrogate must not be reported as the
source-pinned B2 arm; its emitted arm identifier is `B2_SURROGATE`, not `B2`.

The conditional first environment candidate is text-only ALFWorld restricted
to `pick_clean_then_place_in_recep`, recorded in its
[source/data audit](../../_research/causal_composition/priors/alfworld_text_g1_candidate_v1/README.md).
Its simulator terminal state offers a stronger outcome boundary than a static
answer label. Workspace-owner authorization now permits local,
non-redistributive execution of the pinned public bytes; it does not resolve
the release assets' upstream license scope, and redistribution remains blocked.
The aggregate-only clean-task
[pool commitment](../../manifests/HSWM_ALFWORLD_TEXT_CLEAN_POOL_2026-08-30.json)
binds 708 archive-matched text games without publishing their paths or
per-game digests. Its group audit also shows that 25 of 27 `valid_seen` task
groups overlap `train`, whereas none of the 11 `valid_unseen` groups do.
Accordingly, `valid_seen` is a contamination-sensitivity probe, not a
lineage-disjoint final holdout. The
[runtime qualification](../../manifests/HSWM_ALFWORLD_TEXT_RUNTIME_QUALIFICATION_2026-08-30.json)
binds one sealed fixed-action run to exact code, assets, dependencies, sandbox,
and an external private receipt. Its status remains
`ENGINEERING_INSTRUMENT_QUALIFIED_G0_NOT_PASSED`; neither this engineering
qualification nor the pool audit establishes agent efficacy or a G0 decision.
The 11 zero-overlap `valid_unseen` groups remain untouched final-holdout
candidates unless a prospective protocol explicitly allocates them.

Before a live G1 comparison, the next work is limited to four items: implement
and directly parity-check the pinned ExpeL reproduction; qualify an independently
owned outcome/evaluation boundary; freeze a validated task family with fresh
transfer and retention headroom; and connect exactly one HSWM revision kind to
one canonical owner/`Permit` admission path. Only then may a new preregistration
bind a powered B2-versus-H1 estimand and the sham/remove/restore interventions.

The first bounded HSWM revision should be one disposition, such as one route or
one procedure. G1 must not simultaneously invent learned topology, a native
world simulator, a multi-agent society, or model-weight training.

G1 can support the HSWM delta only when:

1. `H1` improves the preregistered fresh outcome over the strongest inherited
   baseline under matched resources;
2. an outcome-independent sham and shuffled or wrong-target credit do not
   reproduce the gain;
3. removing the exact revision removes the gain;
4. byte-identical restoration restores the gain;
5. the compiled behavioral readset is derived from that revision rather than a
   transcript, hidden cache, static prompt, or external memory side channel.

If a prior baseline matches `H1`, HSWM records a useful negative boundary and
does not rebuild the baseline under a new name.

## 6. Research order after G1

Reuse remains gate-specific.

| gate | inherited foundation | unresolved HSWM test |
|---|---|---|
| G2a credit | difference rewards, causal intervention and multi-agent credit methods | calibrated cell/incidence/coalition/whole credit without duplicate inflation |
| G2b coalition | validated fixed, pairwise and centralized multi-agent systems; the withdrawn HyperAgent proposal only as a methodological warning and candidate control shape | role-bearing n-ary coalition has a held-out causal increment without a semantic commander |
| G3 morphogenesis | NCA damage/recovery and learned-graph baselines | owner-valid topology revision improves adaptation and recovery, and lesion/restore mediates it |
| G4 world-self continuity | Dreamer/WALL-E world models, durable memory and lineage systems | world and self state in one graph improves prediction/action across model swap, migration, fork, merge, and damage |
| G5 composition | operadic open-system composition, causal-emergence measures, multiscale competency models | two independently qualified HSWMs form a composite with the same typed learning law and an identifiable macro intervention effect |

No downstream component is implemented merely because its prior exists. The
gate opens only when its predecessor passes.

## 7. Source-of-truth and anti-confound rules

1. The existing HSWM canonical atom and receipt plane remains the sole source of
   HSWM revision identity. An external memory or metagraph store is an adapter
   state, projection, or comparison arm.
2. External components never share hidden cache, vector index, transcript, or
   writable database across experimental arms.
3. The actor, outcome producer, revision proposer, admission authority, and
   evaluator are separately identified in every receipt.
4. Provider-side memory, prompt rewriting, retries, safety transforms, and model
   version drift are either pinned and measured or declared as an attribution
   limitation.
5. Direct-versus-wrapped parity is measured before attributing an effect to the
   imported mechanism.
6. A fixed router or orchestrator may be a baseline, transport mechanism, or
   upper bound. It cannot be relabeled as emergent HSWM coalition or macro
   agency.
7. Repository KG and MCP projections remain documentation and interfaces, not
   cognition or learning.

## 8. What HSWM now builds and does not build

HSWM directly builds only:

1. the common sealed episode, outcome, proposal, resource, and evaluation
   adapter contract;
2. the outcome-credit-owner-`Permit` canonical revision boundary;
3. deterministic compilation from revision to behavioral readset;
4. removal, restoration, rollback, and lineage interventions;
5. later, the same typed boundary at one bounded higher scale.

HSWM does not build a replacement for AtomSpace, Letta, Reflexion, Voyager,
Dreamer, DGM, HyperAgent, NCA, or their full benchmark ecosystems unless a
specific, source-pinned incompatibility makes the claimed intervention
impossible. Even then, only the incompatible seam is reimplemented.

## 9. Relationship to existing repository work

- [`PAPER_CODE_ABSORPTION_LEDGER_2026-07-23.md`](./PAPER_CODE_ABSORPTION_LEDGER_2026-07-23.md)
  remains the source-pinned intake and license boundary.
- [`HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md`](./HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)
  remains the direct-prior and backend audit.
- [`HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md`](./HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md)
  remains the bounded scientific bridge for the eight FCL laws.
- [`../../_research/causal_composition/README.md`](../../_research/causal_composition/README.md)
  remains the gate order and scientific decision contract.

This architecture does not invalidate ongoing exploratory G0 instrumentation.
It prevents that instrumentation from becoming the default HSWM product
architecture and requires the first confirmatory G1 to face inherited, strong,
source-pinned baselines.
