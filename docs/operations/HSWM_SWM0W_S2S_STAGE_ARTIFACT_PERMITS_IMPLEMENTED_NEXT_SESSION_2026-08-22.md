# HSWM SWM-0W-S2S TypeScript/Effect stage-artifact permit handoff

Date: 2026-08-22

Code checkpoint: `01b96ae8080ef9e19100d4a2bd781192498136e4`

Checkpoint parent: `9572be15b343a96ef8959e76b27d69b29ff0f91f`

Authority: the strict TypeScript/Effect direction is `USER_PRIMARY`; this
implementation boundary and continuation order are `SECONDARY_AI_PROPOSED` and
have been independently adversarially reviewed.

Status: `BLOCKED_PRE_PREREG /
STAGE_ARTIFACT_FINITE_PERMIT_AND_LEDGER_ENGINEERING_CLEAR_NONAUTHORIZING_PROBE /
PRODUCTION_CURRENT_RUN_AND_STAGE_READS_IMPLEMENTED_BUT_NOT_ISSUED /
WORKFLOW_SOURCE_BYTES_AND_API_PATH_OPEN /
GITHUB_ORIGIN_NOT_OBSERVED / SCIENTIFIC_UNJUDGED`.

This is the current continuation entrypoint. It supersedes the
[`v7 current-run authority handoff`](HSWM_SWM0W_S2S_RUN_AUTHORITY_IMPLEMENTED_NEXT_SESSION_2026-08-22.md)
only for continuation; v7 remains immutable. Its companion
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v8.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v8.json)
is a local repository KG projection, not HSWM cognition, a remote KG
publication, preregistration, GitHub evidence, or a scientific result.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
Its evolving hypergraph remains one living harness, world model, and continuous
learner. The implemented permit and ledger are a bounded constitutional
interface around one future confirmatory run; they are not cognition, routing,
or learning subsystems.

Only `Π` advanced (`Pi` in the companion machine projection):

- `H`: target identity unchanged; no topology or cognition result;
- `W`: no learned semantic macro-weight or efficacy result;
- `A`: no activation/readout result;
- `F`: no confirmatory function-cell or numeric result;
- `Π`: fixed stage-specific artifact reads, authority-derived finite permits,
  an atomic bounded receipt ledger, fresh identity revalidation, and a closed
  production Layer graph are implemented.

The outcome-bound causal-learning loop did not advance. Event chronology stays
structurally clear only through `1 -> 6 -> 9`; event 10 remains unauthorized.

## Runtime direction

The long-lived control runtime remains strict TypeScript-first with Effect v3:

- TypeScript `5.9.3`, Effect `3.22.1`, Node `24.13.0`;
- immutable observation and evidence classification remain deterministic;
- GitHub acquisition, retained-byte revalidation, resource release, timeout,
  and interruption remain lazy Effects with typed expected failures;
- `Ref.modify` owns atomic permit reservation and ledger admission;
- `Effect.acquireUseRelease` burns an in-flight permit on success, typed
  failure, defect, or interruption;
- production composition is a closed `Layer` with `R = never`;
- Python remains an opaque deterministic numeric oracle.

The `effect-ts-functional` skill governed Effect v3 API selection, typed error
channels, `Ref` atomics, resource safety, Layer closure, and hostile tests. The
`proxmox-runtime-guardrails` skill governed the bounded full verification run.
Neither skill is a runtime dependency or an HSWM capability.

## What code checkpoint `01b96ae` establishes

### Fixed zero-identity stage surface

The public caller-selected artifact method
`observeRoleArtifact(runId, headSha, role)` is gone. The root-private
`S2SStageArtifactReads` union exposes only lazy, zero-argument Effect values:

```text
REGISTER   -> no artifact-read operation
CONFIRM    -> confirmReadRegistration
ADJUDICATE -> adjudicateReadRegistration
              adjudicateReadCandidateFirst
              adjudicateRereadCandidate
```

No operation accepts a token, run ID, head SHA, job ID, stage, role, artifact
ID/name, operation name, or observer. Lookup and validated readback are one
operation, so intermediate authority, artifact identity, and unvalidated bytes
do not escape for a caller-selected second step.

### Authority-derived finite permits

Production first inspects the exact module-issued current-run bearer and derives
run, attempt one, B/head, reviewed workflow API path, run creation identity,
stage, current numeric GitHub job ID, and predecessor numeric job IDs. Copies
and Proxies are not valid bearers.

One root-private production WeakMap preserves state for the same exact bearer.
One bounded module-instance identity slot prevents another genuine bearer from
replenishing permits. The claim is deliberately limited to one trusted worker,
one loaded module copy, one process, and that identity slot. There is no claim
of cross-worker, cross-module-copy, cross-process, or durable replay prevention.

The state transitions are:

```text
permit: ISSUED -> IN_FLIGHT -> SPENT_SUCCESS | SPENT_VOID
stage:  ACTIVE -> IN_FLIGHT -> ACTIVE | COMPLETE | VOID
                                 then CLOSED for a closed test driver
```

Wrong-stage, already-spent, in-flight, or out-of-order requests fail before
state mutation or I/O. Once reservation succeeds, any typed failure, defect, or
interruption spends the permit as `SPENT_VOID` and voids the stage. No retry or
refund path exists.

### One seeded, bounded, non-evicting ledger

Every permit scope begins with the four current-run bracket observations:

```text
CURRENT_RUN_RUN_START
CURRENT_RUN_JOBS
CURRENT_RUN_RUNS_FOR_HEAD
CURRENT_RUN_RUN_END
```

The exact capacities, including those four seed entries, are:

```text
REGISTER = 4
CONFIRM = 16
ADJUDICATE = 40
```

Every freshly standalone-revalidated artifact lookup, job roster, run bracket,
artifact requery, download redirect, and final run read is appended immediately
with `Ref.modify`. Admission is case-sensitive and requires a globally fresh
GitHub request ID, globally fresh receipt SHA-256, monotonic observed second,
available fixed capacity, and the exact per-operation phase topology. Entries
are never evicted. Permit evidence can be sealed only after that operation's
`READBACK_RUN_END` entry.

### Fresh role and artifact binding

Each fixed read revalidates the authority-bound attempt-one run before lookup,
then requires the exact three-job roster, current numeric job, predecessor
numeric jobs, B/head, run creation identity, and job chronology. The artifact's
producer must be the authority-bound predecessor job ID. Run-artifact-list and
single-artifact observations have standalone retained-byte validators.

A negative absence result retains all three independently observed
artifact/run pairs. Adjudication performs two complete candidate reads. Their
fingerprint binds artifact ID/name/size, API digest, downloaded digest, and
validated archive digest; drift voids the final permit and stage.

### Production remains closed and the test seam remains non-authorizing

`makeS2SStageArtifactReadsLiveLayer(registrationAuthority, githubConfig)` fixes
the current-run Layer, production observer, transport, permit scope, and stage
surface and requires no remaining environment. While checked-in workflow bytes
remain `OPEN_UNTIL_WORKFLOW_BYTES_EXIST`, it fails before artifact GitHub
configuration, artifact calls, or permit-scope attachment. The invocation event
file may still be read; the claim is zero artifact configuration/I/O, not zero
local I/O.

`probeS2SStageArtifactReadMechanicsForTest` requires an exact
`TEST_ONLY_NON_AUTHORIZING` fixture, uses a separate WeakMap, returns only
`Effect<void>`, never inspects or issues production authority, and closes its
ephemeral driver. Reusing the same exact fixture cannot replenish permits.

### Bounded redirect residual

The bundled artifact download adapter receives the GitHub redirect response,
then performs the one read-only CDN archive GET before returning the redirect's
GitHub request ID to the permit controller. Therefore a request-ID collision
detected at controller admission can occur after that single CDN GET. On this
path the permit and stage are irreversibly void, no validated read, evidence, or
archive bytes escape, and the final run read is not attempted. The CDN request
has no GitHub authorization header, is timed and byte-bounded, and is not
retried.

This is an explicit claim boundary, not durable replay protection. A future
claim of “no physical downstream I/O after detected replay” must split redirect
admission from archive retrieval or inject the shared ledger guard into the
transport before the CDN fetch.

## Verification

The code checkpoint passed:

- focused stage-artifact suite: `22/22`;
- focused GitHub validator/adapter suite: `32/32`;
- focused current-run authority suite: `30/30`;
- package-root containment suite: `2/2`;
- full package suite: `218/218` tests in `16/16` suites;
- strict TypeScript check, build, `npm pack --dry-run`, and diff check;
- independent read-only permit-core and GitHub-adapter adversarial audits with
  no finite-permit gate blocker in the declared process-slot scope.

The full command ran through bounded Proxmox scratch:

```text
cd src/hswm/effect-runtime
proxmox-scratch run hswm-effect-stage-permits-v8 --timeout 7200 -- npm run verify
```

The scratch directory was removed and no long-lived worker remained. These are
engineering results only: no production Layer or genuine issuer executed, no
GitHub origin was established, and no numeric or scientific verdict exists.

## Exact next-session order

1. Read the constitution, this handoff, the v8 KG, immutable v7, and the
   `effect-ts-functional` skill. Preserve the two protected user changes.
2. Treat `01b96ae` as the exact implemented code checkpoint. Keep the
   production permit service dormant until reviewed workflow source, manifest,
   and API-path bindings allow genuine current-run issuance.
3. Define a content-addressed, create-only durable evidence envelope and closed
   `register`, `confirm`, and `adjudicate` stage programs. Fix executable
   entrypoints and mandatory-upload postconditions before writing workflow
   YAML. Do not infer durable or cross-process uniqueness from `Ref`, WeakMap,
   or the module identity slot.
4. Implement the terminal finalizer and rerun-invalidation rule. Its last fresh
   attempt-one run, jobs, runs-for-B, and artifact observations must occur
   immediately before create-only durable publication. An earlier stage ledger
   does not close that race.
5. Adversarially enumerate the closed programs' complete failure/VOID matrix,
   including upload/postcondition failure and interruption, before source
   freeze. Preserve the bounded redirect residual unless the stronger no-I/O
   claim is explicitly required.
6. Only after those execution surfaces are closed, author and independently
   review the exact three-job workflow. Pin its literal raw SHA-256, resulting
   workflow-contract digest, matching exact `100644 blob` source-A manifest
   row, and one literal workflow API path representation.
7. Then add the genuine positive production Layer/issuer/inspector regression.
   A real positive observation may establish GitHub origin and issuance; the
   current synthetic probe never can.
8. Do not create source freeze, preregistration, a future beacon, dispatch,
   candidate, adjudication, or event 10 merely to advance engineering. Those
   require their own evidence-supported gate decisions.

Routine implementation and documentation do not require a content-addressed
research receipt or an `F1_R8_RESULTS_LOG.md` entry.

## Protected scope and nonclaims

These pre-existing user changes remain uncommitted and protected:

- `src/hswm/experiments/continual_live.py`
- `tests/test_hswm_continual_live.py`

No remote KG was mutated. No workflow source, reviewed API path, source-A
workflow row, GitHub-origin observation, genuine current-run or stage-read
capability, durable envelope, terminal finalizer, preregistration, beacon,
dispatch, candidate, adjudication, event-10 verdict, learned `W`, or
outcome-bound causal update was created.

## Minimal continuation prompt

```text
Continue HSWM from code checkpoint
01b96ae8080ef9e19100d4a2bd781192498136e4. Read
docs/canon/HSWM_CONSTITUTION_2026-08-20.md,
docs/operations/HSWM_SWM0W_S2S_STAGE_ARTIFACT_PERMITS_IMPLEMENTED_NEXT_SESSION_2026-08-22.md,
ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v8.json, immutable v7, and the
effect-ts-functional skill. Preserve the two continual_live changes. Stay
strict TypeScript/Effect v3 with Python numeric-only. Fixed zero-identity stage
artifact Effects, process/module-slot-scoped one-use permits, the seeded
bounded request ledger, fresh job/artifact validation, and independent
candidate reread are engineering-clear under a non-authorizing probe.
Production remains WORKFLOW_SOURCE_BYTES_OPEN and has issued nothing; do not
claim GitHub origin or durable/cross-process replay prevention. Next implement
the content-addressed create-only durable evidence envelope, closed stage
programs and mandatory-upload postconditions, then the fresh terminal
reobservation/rerun-invalidation finalizer and full failure/VOID review. Only
after those surfaces are closed should you author/review workflow YAML, pin its
raw SHA, contract digest, source-A manifest row, and one API path, and add a
genuine production issuance regression. Do not create preregistration, beacon,
dispatch, candidate, adjudication, or event 10 merely for engineering progress.
```
