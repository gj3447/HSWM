# HSWM SWM-0W-S2S pre-freeze resource-policy review decision — next-session handoff

Date: 2026-08-23
Workspace parent: `866b2fbd3fc98311c8a0254124dfc0444758adec`
Continuation KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v25.json`
Predecessor KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v24.json`
Status: `75/245/75 REJECTED FOR PRODUCTION OR PREREGISTRATION FREEZE / ARITHMETIC FIXTURE RETAINED / FULL-SCALE TIMING EVIDENCE REQUIRED / SCIENTIFICALLY UNJUDGED`

## Resume capsule

`SWM0W_S2S_PRE_FREEZE_RESOURCE_POLICY_REVIEW_V1` is complete. The exact
`75/245/75` minute REGISTER/CONFIRM/ADJUDICATE amendment is internally valid
addition, and every value is below GitHub's current six-hour hosted-job limit.
It is nevertheless rejected as a production or preregistration freeze.

The rejection is not an efficacy judgment and does not say that a 245-minute
CONFIRM job is intrinsically too short or too long. It says that this exact
three-stage policy lacks the evidence and global chronology coherence required
by the repository's own S2S gate:

- only one successful hosted train/dev pilot job exists, so no workflow p95 was
  measured;
- the pilot covered three disclosed tuning draws, not the intended 20-task
  end-to-end stage shape;
- two of three selected T16 draws reached the 300-update cap, while P_CAP18 and
  DS870 followed epoch-zero/patience paths, so the telemetry is not a
  convergence or max-budget upper bound;
- the candidate's 75-minute REGISTER job exceeds the existing maximum
  workflow-created-to-pulse lead of 65 minutes even though registration must
  complete strictly before the pulse;
- REGISTER's claimed 20-minute preparation basis is copied from the existing
  register job timeout, despite the candidate declaring that preparation comes
  from a command/work budget rather than an old job timeout;
- the hosted continuity probe used a different test-only upload-action pin,
  small structural payloads, 20/10-minute probe timeouts, and no successful
  CONFIRM upload; and
- no future S2S production workflow, source A, preregistration B, full candidate
  archive, or production readback occurrence exists.

Therefore the v24 object remains only a package-internal arithmetic and hostile
validation fixture. This checkpoint does not choose a replacement timeout,
change the provisional TypeScript policy hash, mutate any workflow or protocol
config, create preregistration, or open future randomness.

The exact next gate is
`SWM0W_S2S_RESOURCE_POLICY_CHRONOLOGY_AND_TIMING_PROTOCOL_DESIGN_V1`. It must
define a future-seed-free, disclosed full-scale resource profile before any
heavy run is dispatched. The subsequent evidence occurrence is named
`SWM0W_S2S_DISCLOSED_FULL_SCALE_RESOURCE_PROFILE_V1`.

## Canonical role, current evidence, and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
`docs/canon/HSWM_CONSTITUTION_2026-08-20.md`. Its evolving `H/W/A/F/Pi` is one
living harness, world model, and continuous learner. TypeScript, Effect,
Python, GitHub workflows, artifacts, and this repository KG are bounded
interfaces and projections; they are not HSWM cognition or learning by
themselves.

The target causal loop remains:

```text
role-bearing n-ary H
  -> recipient-conditioned semantic transport W
  -> token activation A
  -> typed LLM function cell F
  -> attributable external outcome
  -> causal credit
  -> accepted versioned delta-W/delta-H under Pi
  -> changed next activation or behavior
```

This review changes none of that loop:

| Axis | Current evidence after v25 |
|---|---|
| `H` | Unchanged. No canonical persistent relation, topology rewrite, or provenance edge was added. |
| `W` | Unchanged. The internal fixed T16 projection was not trained, updated, exported, or composed with scalar outcome credit. |
| `A` | Unchanged. No token trajectory, recurrence, routing, or next-episode behavior was added. |
| `F` | Unchanged. No LLM-executed typed function cell or efficacy result was added. |
| `Pi` | Review-only advance. One misleadingly feasible arithmetic candidate is now explicitly barred from production/preregistration freeze until chronology and full-scale resource evidence pass. |
| Outcome-bound causal learning | Not advanced. No attributed outcome, credit authorization, durable state transition, rollback, or changed next behavior occurred. |

The conceptual delta from v24 is one claim-boundary decision, not a runtime
feature: `CANDIDATE_PENDING_REVIEW -> REJECTED_FOR_FREEZE_RETAINED_AS_ARITHMETIC_FIXTURE`.
Tests and KG bindings are evidence instruments for that decision; they do not
constitute scientific S2S progress.

## Reviewed evidence

### Disclosed pilot and convergence boundary

The accepted train/dev pilot remains GitHub Actions run `32442437970` at source
`75686549b1f6c65aea87ebd0f912a6e62909445a`. It is the only successful run for
the repaired pilot source. The earlier run `32441694463` failed before task
preparation and contributes no runtime sample.

The accepted occurrence records:

| Observation | Value |
|---|---:|
| GitHub job elapsed | `1,361 s` |
| Stage-one 27-cell fit + replay | `132,795,963,591 ns` |
| Stage-two 27-cell fit + replay | `1,204,235,087,351 ns` |
| Selected-rate nine-cell fit + replay | `424,904,259,742 ns` |
| Three task preparations | `2,340,178,403 ns` |
| Observed process high-water RSS | `171,108 KiB` |

The provisional TypeScript scaffold projects 20-task pre-evaluation work as
`3,069,388,354,600 ns`, or about `51.16 min`, against a `120 min` post-seed
work cap. That leaves a nominal `68.84 min` reserve. This is a planning
projection from one workflow and three tuning draws, not a repeated p95,
distribution-free upper bound, production end-to-end observation, or guarantee
that every allowed 300-update path fits.

The adopted numerical settings remain exact engineering candidates:

- T16 learning rate `0.003`;
- P_CAP18 and DS870 learning rate `0.001`;
- seed `0`, maximum updates `300`, patience `50`, minimum delta `1e-9`, and
  gradient clip `5` for every arm;
- task count `20`, fixed generator and with-replacement collision retention;
- bootstrap `10,000`, PCG64 seed `20260820`, task-only resampling, and shared
  indices; and
- essential `Q/B/R` lower-bound thresholds `0.80/0.10/0.10`.

Two selected T16 draws reached the update cap. The allowed interpretation is
therefore a fixed-budget estimator only. No convergence, global optimum, or
post-outcome budget extension is allowed. P_CAP18 and DS870 selected epoch zero;
the DS-derived compact-competitive phrase remains prohibited.

The scientific gate explicitly required arm/task update timing, peak memory,
and workflow p95 before timeout freeze. No checked-in artifact supplies a
workflow p95. The pilot report itself records timeout/archive policy as
`PENDING_NOT_CHOSEN`.

### Exact arithmetic and its limits

The v24 candidate adds the following components:

| Stage | Preparation | Upload | Whole assertion | Reconcile/finalize | Margin | Total |
|---|---:|---:|---:|---:|---:|---:|
| REGISTER | 20 min | 10 min | 30 min | 10 min | 5 min | 75 min |
| CONFIRM | 190 min | 10 min | 30 min | 10 min | 5 min | 245 min |
| ADJUDICATE | 20 min | 10 min | 30 min | 10 min | 5 min | 75 min |

The Effect validator correctly rejects additive drift, fractional or unsafe
budgets, an inexact margin, non-whole-minute values, and hosted-cap overflow.
That validator proves only the local arithmetic contract.

The global chronology does not close. The provisional policy allows at most
`3,900 s = 65 min` from workflow creation to the committed pulse and requires
registration completion strictly before that pulse. A 75-minute REGISTER job
timeout can cross the pulse. A future design must either reduce the full
REGISTER bound or revise and revalidate the pulse-lead hierarchy; it cannot
freeze both current facts simultaneously.

The component provenance is also incomplete:

- the 30-minute whole-assertion timeout is an implemented Effect timeout;
- CONFIRM's 190 minutes correspond to wait + post-seed work + command slack;
- ADJUDICATE has a 20-minute command bound;
- REGISTER has no separate 20-minute command/work bound in the provisional
  policy; its matching 20-minute value is the old whole-job timeout; and
- the candidate-only 10-minute upload, 10-minute reconcile/finalize, and
  5-minute margin are not yet independently enforced production phase limits.

### Provider feasibility is not policy sufficiency

GitHub's current official Actions limits allow a standard hosted job to execute
for at most six hours. All three arithmetic totals are below that ceiling. The
official public-repository artifact setting also permits at most 90 days, so the
provisional 90-day value is provider-admissible. These facts establish only
platform feasibility, not scientific sufficiency or durable evidence.

Primary references rechecked on 2026-08-23:

- https://docs.github.com/en/actions/reference/limits
- https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository

The accepted pilot ZIP is about 1.36 MiB. The test-only continuity artifacts
are much smaller structural shapes. Neither validates an intended 20-task
candidate member, the `4/64/4 MiB` REGISTER/CANDIDATE/ADJUDICATION archive caps,
the 60 MiB candidate-member cap, production upload/readback time, 90-day
availability, or external durable recovery.

## Do not conflate three distinct policy surfaces

1. `src/hswm/effect-runtime/src/s2s-confirmatory.ts` contains a hash-pinned,
   unexecuted engineering scaffold with `20/210/30` minute job deadlines,
   a 120-minute post-seed work cap, and provisional archive limits. Its comment
   says “frozen,” but no scientific preregistration adopted it.
2. `.github/workflows/swm0w-confirmatory.yml` and
   `prereg/PREREG_SWM0W_SCALAR_GATE_V1.json` belong to the historical scalar
   experiment. Their `20/300/30` timeouts and source hashes are not the future
   S2S workflow and must not be edited as an S2S amendment.
3. The intended future S2S paths are
   `.github/workflows/swm0w-s2s-confirmatory.yml` and
   `prereg/PREREG_SWM0W_S2S_GATE_V1.json`. Both are absent. The workflow
   contract keeps its source SHA status `OPEN_UNTIL_WORKFLOW_BYTES_EXIST`, and
   production run authority fails closed.

Accordingly, TypeScript literals and hashes are engineering identity, not
scientific authority. V25 leaves all three surfaces unchanged.

## Decision matrix

| Question | Decision |
|---|---|
| Is `75/245/75` exact addition? | `YES` |
| Is each value below the current hosted-job hard cap? | `YES` |
| Is REGISTER globally compatible with the current 65-minute pulse-lead maximum? | `NO` |
| Is there a repeated workflow p95? | `NO` |
| Was the intended 20-task end-to-end production shape observed? | `NO` |
| Was the production upload-action and CONFIRM upload/readback path timed? | `NO` |
| Do the observations prove convergence or max-budget runtime? | `NO` |
| Are full candidate/adjudication archive sizes and durability established? | `NO` |
| Is the exact future S2S workflow/source/preregistration present? | `NO` |
| May the candidate be frozen into production or preregistration? | `NO` |
| May the object remain as a non-authorizing arithmetic fixture? | `YES` |

Formal decision:

```text
SWM0W_S2S_PRE_FREEZE_RESOURCE_POLICY_REVIEW_V1
  = REJECT_EXACT_75_245_75_PRODUCTION_FREEZE_REVISE_REQUIRED
  / RETAIN_AS_TEST_ONLY_ARITHMETIC_FIXTURE
  / NO_REPLACEMENT_POLICY_SELECTED
```

## Preregistration completeness and independent claim boundaries

The preregistration state remains `NOT_READY / BLOCKED_PRE_PREREG`.

- The adopted protocol config is
  `CANDIDATE_PROTOCOL_ENGINEERING_ONLY_UNJUDGED`, not a scientific freeze.
- No source A, direct-child add-only B, future round, registration-authority
  occurrence, production workflow byte hash, or S2S preregistration exists.
- Production process continuity, shared durability, complete-stage recovery,
  GitHub origin, artifact readback authority, and external exactly-once behavior
  remain open.
- No future seed, confirmatory task, test split, Q/B/R reducer, event 10, or
  scientific verdict was opened.

The three essential scientific quantities `Q`, `B`, and `R` share the same 20
tasks and the same bootstrap indices. They are conjunctive co-primary claims,
not independent samples. Task draws are indexed with-replacement samples from
one fixed feature-frame generator, not independent mechanisms. Worlds and the
12 outputs of a world are never bootstrap units. The optional `C` phrase is
disabled and cannot rescue or modify the essential gate.

## Exact next evidence path

### First: protocol design, no heavy execution

`SWM0W_S2S_RESOURCE_POLICY_CHRONOLOGY_AND_TIMING_PROTOCOL_DESIGN_V1` must pin:

1. an end-to-end deadline inequality in which REGISTER necessarily completes
   before the pulse and every phase fits inside its job timeout;
2. the exact intended runner image, Python/uv/Node/Effect versions, thread
   envelope, production upload-action SHA, and workflow source bytes;
3. a disclosed, future-seed-free task source whose every timing task is excluded
   from later efficacy evidence;
4. the exact 20-task, three-arm, 60-cell, fit+replay workload and whether the
   timing profile includes the full evaluation/adjudication path;
5. max-budget behavior for all three arms, including how 300-update
   cap-saturation is measured or bounded without using test outcomes;
6. the workflow repetition count, empirical p95 estimator, uncertainty or
   conservative upper-envelope rule, RSS rule, archive-size rule, and acceptance
   inequality before observing new timings;
7. phase-specific preparation, upload, assertion, reconcile/finalize, and
   cleanup measurements rather than one undifferentiated job duration;
8. exact production-shaped candidate upload and immediate downloaded readback;
9. no retry, rerun, resume, task skip, timeout extension, or task/threshold/
   optimizer change after observing timing or scientific outputs; and
10. typed VOID/FAIL outcomes for timeout, OOM, partial output, missing upload,
    readback failure, archive overflow, chronology violation, or runtime drift.

Do not dispatch the full-scale profile while any item above is open.

### Then: disclosed full-scale resource occurrence

`SWM0W_S2S_DISCLOSED_FULL_SCALE_RESOURCE_PROFILE_V1` may use only the frozen
timing protocol. It must not open the future confirmatory seed or materialize a
confirmatory test split. Acceptance requires the predeclared p95/upper-envelope,
RSS, archive, upload/readback, and chronology conditions to pass. Only then may
a new review accept or revise the timeout/archive policy and compute a new
resource-policy hash.

After that separate acceptance, and not before, source A and the exact future
workflow may be frozen, an add-only preregistration B may be created, and a
future public round may be selected.

## Effect/TypeScript and runtime boundary

The complete `effect-ts-functional` skill was applied against the pinned stack:
TypeScript `5.9.3`, Effect `3.22.1`, Node `24.13.0`, and Vitest `3.2.7`.
No Effect v4 API or imperative orchestration path was introduced. The existing
pure arithmetic validator, typed failures, strict schema boundary, scoped
lifecycle implementation, and package-private production capabilities remain
unchanged.

That skill influenced this checkpoint by keeping a policy review out of the
numeric core and by treating typed literals as engineering data rather than
runtime or scientific authority. The Proxmox runtime guardrails also kept this
review read-only/lightweight: no heavy local experiment, repeated agent loop,
shared MCP change, or hosted timing dispatch occurred.

## Verification and research ceremony

This checkpoint changes documentation, the local continuation KG, successor-
aware handoff verification, and indexes only. It does not change runtime
implementation, policy literals, workflows, numerical config, or scientific
evidence.

The exact verification results are recorded in the v25 KG after generation.
This review is routine research-program governance, not a material scientific
result. It requires no content-addressed result receipt and no new
`F1_R8_RESULTS_LOG.md` entry.

## Exact next-session order

1. Read the constitution, Occam core, S2S gate, v24 handoff/KG, this decision,
   v25 KG, and the complete `effect-ts-functional` skill.
2. Preserve the unrelated dirty files
   `src/hswm/experiments/continual_live.py` and
   `tests/test_hswm_continual_live.py`.
3. Treat `75/245/75` as rejected for freeze and retained only as an arithmetic
   fixture. Do not silently adopt the older `20/210/30` scaffold instead.
4. Keep the historical scalar workflow/preregistration immutable and distinct
   from the absent S2S paths.
5. Design `SWM0W_S2S_RESOURCE_POLICY_CHRONOLOGY_AND_TIMING_PROTOCOL_DESIGN_V1`
   before writing or dispatching a heavy timing workflow.
6. Do not open future randomness, confirmatory tasks, source A/B, event 10, or
   any Q/B/R judgment during timing design or profiling.
7. Keep the T16 package-root export and scalar-credit composition refused until
   their separate source-provenance/state-ownership gate is reviewed.
8. Keep SWM-1, recurrence, LLM function cells, causal learning, topology
   learning, and every broad HSWM completion claim downstream of supported
   evidence.

## Exact nonclaims

No replacement production timeout, archive freeze, policy hash, workflow,
source A, preregistration B, future seed, confirmatory dispatch, test outcome,
Q/B/R statistic, event 10, scientific verdict, TypeScript training, public T16
API, scalar/operator composition, token-native recurrence, LLM function cell,
causal delta-W/delta-H, topology mutation, remote KG publication, or complete
HSWM was produced. The repository KG remains a bounded continuation projection.
