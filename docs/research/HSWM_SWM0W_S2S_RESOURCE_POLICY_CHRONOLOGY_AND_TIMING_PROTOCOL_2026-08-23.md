# HSWM S2S resource-policy stop decision

- Date: 2026-08-23
- Status: `POLICY_DECISION_CLOSED / EXECUTABLE_BINDINGS_OPEN / NON_DISPATCHABLE`
- Next gate: `SWM0W_S2S_RESOURCE_PROFILE_WORKFLOW_AND_COLLECTOR_SOURCE_FREEZE_V1`

## Canonical role and current evidence

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
Repository ontology, KG records, workflows, TypeScript, Effect, Python, tests,
and receipts are bounded projections and evidence interfaces; none is HSWM
cognition or learning by itself.

At pre-fix main `6d72168fd07aa141f6ca5b96d4278793dd2571ce`, the repository
delta after S2S pilot adoption commit `a4bff3b` was directly re-counted as 50
commits, 177 changed files, 106,955 additions, and 23 deletions. The repository
held handoff KG v1 through v25 and 23 versioned Python handoff tests. The latest
v25 record still stated:

- `H/W/A/F`: unchanged;
- outcome-bound causal-learning loop: not advanced;
- `Pi`: review-only narrowing; and
- scientific status: `UNJUDGED`.

The protected user work in `continual_live.py` and its test is uncommitted and
is excluded from those counts and from this decision.

Inference: evidence transport and version ceremony grew much faster than causal
evidence. This is a research-allocation failure signal, not evidence that HSWM
itself is refuted. The corrective action is to stop transport-layer growth and
return to bounded falsifiers.

## Stop decision

This file is the final resource-policy design record. Do not create a v26/v27
handoff, successor KG, design-only TypeScript schema, or another handoff test.
No receipt or `F1_R8_RESULTS_LOG.md` entry is warranted because no material
research result was produced.

Existing v1-v25 records and versioned handoff tests remain historical files,
but the versioned tests are retired from the default pytest/CI surface. Their
current-document hash checks turned history into a forward-write gate and made
an honest `EFFICACY.md` correction fail unrelated core tests.

The workflow-p95 prerequisite in
[`HSWM_SWM0W_S2S_GATE_2026-08-20.md`](HSWM_SWM0W_S2S_GATE_2026-08-20.md)
and v25 is superseded for this decision. Estimating p95 would require a repeated
population study and would recreate the transport campaign this stop decision
rejects. Exactly one occurrence may describe or falsify that occurrence only;
it cannot estimate a distribution or freeze a production timeout.

## One permitted profile occurrence

After the next source-freeze gate and explicit dispatch authorization, exactly
one workflow run ID at `run_attempt = 1` may profile one disclosed 20-task
batch. The frozen workload is:

- arms `T16`, `P_CAP18`, and `DS870` in that order;
- 60 task-arm cells and exact fit/replay for each cell;
- the adopted natural configuration: seed 0, maximum 300 updates, patience 50,
  gradient clip 5, and learning rates `0.003/0.001/0.001`;
- sealed natural best states as the only candidate source; and
- full production-shaped evaluation, upload, downloaded readback, and
  optimizer-free adjudication.

A timing-only continuation to update 300 is allowed only if the source freeze
adds a seam that captures terminal parameters and Adam state without changing
natural receipt bytes, exposes no test/scientific value to the resource
collector, and destroys the continuation state before evaluation. The current
Python trainer does not expose this seam, so dispatch remains forbidden.

Natural early stopping may branch on its already-frozen dev loss. Scientific
reducers may compute their already-frozen results. Those values remain opaque
to resource disposition: no score, loss, interval, or verdict may change
dispatch, configuration, caps, retries, or the resource terminal.

## Chronology and resource boundary

Registration uses arithmetic accounting only; there is no 3,900-second sleep
and no future-randomness contact:

```text
observed(workflow_created -> registration_downloaded_readback) + 300 < 3,900
accounted_future_CONFIRM = 3,900 + observed_profile_CONFIRM_work
```

The rejected `75/245/75` minutes remain a test-only arithmetic fixture, not a
production policy. The one occurrence tests these declared hypotheses:

- natural plus timing-continuation work: at most 7,200 seconds;
- accounted CONFIRM preparation/command: `3,900 + 7,200 + 300 = 11,400`
  seconds;
- upload 600 seconds, downloaded readback 1,800 seconds, cleanup 600 seconds,
  and explicit margin 300 seconds; and
- archive/member admission: REGISTER 4 MiB, candidate ZIP 64 MiB with one
  candidate member at most 60 MiB, ADJUDICATE 4 MiB.

GitHub-hosted job hard timeouts are external censoring limits, not successful
measurement thresholds. REGISTER uses 4,500 seconds; CONFIRM and ADJUDICATE use
the currently documented maximum 21,600 seconds. Controlled computation must
stop at its declared hypothesis boundary while enough job time remains for
telemetry, upload/readback, and process-group cleanup. A provider hard kill is
`INCONCLUSIVE`, never a valid `RESOURCE_FALSIFIED` receipt. GitHub says limits
are subject to change, so source freeze must reread the official
[Actions limits](https://docs.github.com/en/actions/reference/limits).

Terminals are deliberately small:

- `RESOURCE_FEASIBLE_FOR_SEPARATE_REVIEW_ONLY`: this one occurrence completed
  under every frozen bound; it selects no production policy;
- `RESOURCE_FALSIFIED`: a controlled timing, memory, archive, or chronology
  hypothesis was observed false with valid telemetry and cleanup;
- `VOID_PROTOCOL`: identity/digest drift, duplicate run, mutation, retry,
  replacement, science-dependent resource branching, or continuation leakage;
  and
- `INCONCLUSIVE`: provider/API unavailability, external cancellation, missing
  required cgroup-v2 evidence, or other right censoring.

There is no retry, rerun, resume, replacement, timeout extension, task skip, or
post-observation mutation.

## What the next source freeze must bind

All of the following remain `OPEN`; therefore the profile is non-dispatchable:

```text
SOURCE_COMMIT_OID_AND_GITHUB_SHA_EQUALITY
SINGLETON_DISPATCH_AUTHORITY_AND_OCCURRENCE_SLOT
CONCURRENCY_GROUP_AND_FIRST_RUN_SELECTION_RULE
DISCLOSED_SEED_AND_20_TASK_ROSTER
STRUCTURAL_TASK_AND_TARGET_EXCLUSION_SETS
STRUCTURAL_EXCLUSION_REDUCER_CAPABILITY
PROFILE_WORKFLOW_AND_COLLECTOR_SOURCE_HASHES
CONTINUATION_SEAM_AND_STATE_SCHEMA_HASHES
MACHINE_CONTRACT_AND_RUNNER_IMAGE_OBSERVATION
FULL_OCCURRENCE_RECEIPT_SCHEMA
```

`refs/heads/main` is trigger metadata only, never frozen source identity. The
current adopted reducer checks provenance exclusions but not structural task or
target collisions; the source freeze must add that capability before making
the future-collision `VOID` rule enforceable. Any second run ID, even with
`run_attempt = 1`, is `VOID_PROTOCOL` and receives no replacement.

New orchestration, collector, resource, concurrency, and adapter code is
TypeScript-first on pinned Effect v3, using functional-core/effect-shell,
typed errors, scoped resources, and explicit Python numeric-kernel adapters.
No design-only Effect wrapper is added here; code begins only with the
executable source-freeze gate.

## Research order after this stop

1. restore main CI and correct the P1v2->P1v4/L1 efficacy boundary;
2. freeze the one executable TypeScript/Effect workflow and collector;
3. with explicit authorization, run the bounded profile exactly once;
4. separately preregister and run one S2S confirmatory for `PASS` or `KILL`;
5. run the decisive L1 causal-lesson falsifier: outcome -> learned typed state
   -> stronger than no-memory/raw/shuffled/removed controls -> content-addressed
   `delta-W/delta-H` -> changed next behavior.

Until step 5 succeeds, `H/W/A/F` and the causal loop remain unchanged. If L1
fails, the honest scope contracts toward a strong compiler plus safe static
graph memory.
