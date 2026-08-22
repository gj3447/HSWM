# HSWM SWM-0W-S2S TypeScript/Effect current-run authority handoff

Date: 2026-08-22

Code checkpoint: `dd381f341c08057356ba3e70c83fca33714094b6`

Checkpoint parent: `6fb5fc394ae034713a60fe1a6e6712e00d919e3b`

Authority: the strict TypeScript/Effect direction is `USER_PRIMARY`; this
implementation, claim boundary, and continuation order are
`SECONDARY_AI_PROPOSED` and have been independently adversarially reviewed.

Status: `BLOCKED_PRE_PREREG /
CURRENT_RUN_ACQUISITION_AND_POLICY_ENGINEERING_CLEAR_NONAUTHORIZING_PROBE /
PRODUCTION_AUTHORITY_IMPLEMENTED_BUT_NOT_ISSUED /
WORKFLOW_SOURCE_BYTES_AND_API_PATH_OPEN /
GITHUB_ORIGIN_NOT_OBSERVED / SCIENTIFIC_UNJUDGED`.

This is the current continuation entrypoint. It supersedes the
[`v6 observation implementation handoff`](HSWM_SWM0W_S2S_OBSERVATION_AUTHORITY_IMPLEMENTED_NEXT_SESSION_2026-08-22.md)
only for continuation. The v6 checkpoint remains immutable. Its companion
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v7.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v7.json)
is a local repository KG projection. It is not HSWM cognition, a remote KG
publication, preregistration, GitHub evidence, or a scientific result.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
Its evolving hypergraph remains one living harness, world model, and continuous
learner. This run gate is a bounded constitutional interface; it is not a
router, cognitive subsystem, learning event, or replacement for `H/W/A/F`.

This checkpoint advances only `Pi`:

- `H`: target identity unchanged; no topology or cognition result;
- `W`: no learned semantic macro-weight or efficacy result;
- `A`: no activation/readout result;
- `F`: no confirmatory function-cell or numeric result;
- `Pi`: authentic input binding, a bounded request-distinct current-run bracket,
  typed stage-entry policy, capability containment, and a closed production
  Layer graph are implemented.

The outcome-bound causal-learning loop did not advance. Event chronology stays
structurally clear only through `1 -> 6 -> 9`; event 10 remains unauthorized.

## Runtime direction

The long-lived control runtime remains strict TypeScript-first with Effect v3:

- TypeScript `5.9.3`, Effect `3.22.1`, Node `24.13.0`;
- immutable observation/evidence classification is a deterministic kernel;
- GitHub acquisition, byte revalidation, timeout, interruption, and Live
  composition are lazy Effects with typed expected failures;
- `Context.Tag` provides dependency identity but is never treated as authority;
- module-issued WeakMap capabilities and their inspectors provide process-local
  authenticity;
- production uses `Layer.provide`, not `provideMerge`, and exposes a closed
  `R = never` Layer;
- Python remains an opaque deterministic numeric oracle.

The `effect-ts-functional` skill governed version routing, functional-core /
Effect-shell design, typed errors, Layer closure, and verification. The
`proxmox-runtime-guardrails` skill governed the bounded full verification run.
Neither skill is a runtime dependency or HSWM capability.

## What code checkpoint `dd381f3` establishes

### Authentic registration and current-invocation binding

The new root-private module is
[`s2s-run-authority.ts`](../../src/hswm/effect-runtime/src/s2s-run-authority.ts).
The production Layer accepts only a registration-B capability and GitHub token
configuration. It fixes `S2SCurrentInvocationLive` and, once activation is
allowed, the HTTP-Live-to-observer-Live graph. There is no constructor argument
for run ID, head SHA, stage, workflow path/hash, observer Layer, or `allowOpen`.

Before any GitHub observation, the core inspects the exact module-issued
registration and invocation objects through their existing WeakMaps. It derives
`A`, `B`, run ID, attempt, job, and stage only from those inspected snapshots and
requires:

```text
registration.sourceCommitA == invocation.pushBeforeSha
registration.registrationCommitB == invocation.pushAfterSha
invocation.commitSha == invocation.workflowSourceCommitSha == B
invocation.workflowContractSha256 == checked-in contract SHA-256
```

Copies and transparent Proxies of genuine input capabilities fail because they
are not the exact WeakMap keys. An authentic but internally valid invocation
whose A/B differs from the registration capability also fails before GitHub.

### Exact request-distinct stage-entry bracket

The dormant pinned production core and the non-authorizing test probe share one
lazy sequential acquisition path:

```text
run-start -> attempt-one jobs -> workflow-runs-for-B -> run-end
```

Each returned wrapper is immediately passed through the standalone raw-byte
revalidator using the independently derived run ID or B. There are no retries,
sleeps, parallel reads, or caller-selected identities. The aggregate bracket
timeout is 480 seconds; external interruption and defects remain interruption
and defects rather than being laundered into expected errors.

The policy requires:

- four case-sensitive, pairwise-distinct GitHub request IDs;
- `invocation capture <= start <= jobs <= roster <= end`, allowing equal seconds;
- exactly one exact-head roster row, whose run ID is the authentic invocation
  run ID;
- attempt one and stable repository, head repository, B, workflow name, event,
  branch, reviewed API path, creation string, and creation Unix second across
  start/roster/end;
- start and end direct reads remain `in_progress` with null conclusion;
- a nonterminal roster state may lag, but a terminal roster contradiction is
  rejected;
- exactly the three fixed `register`, `confirm`, and `adjudicate` jobs;
- all job rows bind the authentic run, attempt one, and B;
- exactly one current invocation job is in progress with null conclusion and
  completion;
- every earlier fixed job exists exactly once, completed successfully, and is
  chronologically ordered before the current job;
- every later fixed job remains nonterminal and inactive.

No runner-label claim is made. The workflow API path policy deliberately
supports two test representations, unsuffixed and `@main`, but production has
not selected either. One literal representation must be pinned with reviewed
live semantics before activation.

### Evidence and capability scope

A successful private production classification is prepared to form one frozen,
self-hashed evidence record binding:

- registration and invocation receipt hashes;
- A and B;
- contract, workflow-file, and tracked-manifest hashes;
- workflow run/stage/current job identities and predecessor numeric job IDs;
- all four observation receipt hashes, request IDs, and timestamps.

The evidence makes these limits machine-readable:

```text
authorityScope = PROCESS_LOCAL_STAGE_ENTRY
uniquenessClaim = ROSTER_OBSERVATION_INSTANT_ONLY
historicalUniquenessClaimed = false
crossExecutionReplayPreventionClaimed = false
durableCommitRequiresFreshTerminalObservation = true
```

The capability brand, issuer, full bracket snapshot, and module-global WeakMap
remain private. The exported direct-module inspector accepts only the exact
issued object. A `Context.Tag` value alone is not authority. A retained issued
object would remain inspectable across Layer scopes in the same process, so
this checkpoint does not claim Layer-local revocation or one-use spending.
Finite stage permits and durable replay prevention remain later gates.

### Production remains honestly closed

The checked-in workflow contract still says
`OPEN_UNTIL_WORKFLOW_BYTES_EXIST`, and the workflow file is absent. Production
therefore:

1. captures and validates the authentic current invocation;
2. authenticates registration B and cross-binds A/B;
3. returns typed `WORKFLOW_SOURCE_BYTES_OPEN`;
4. does not construct, configure, or call the GitHub observer/transport.

The intentional invocation event-file read is not described as zero I/O. The
verified claim is zero GitHub configuration/API work while source bytes are
OPEN. A malformed or cross-mismatched authentic invocation fails before OPEN,
as it should.

The pinned production Layer, private issuer, and genuine current-run capability
have never executed. Activation requires all of the following first:

- reviewed workflow bytes and one literal workflow-file SHA-256;
- the matching exact `100644 blob` source-A manifest row;
- a reviewed workflow API path representation;
- a positive Layer/issuer/inspector regression using the real reviewed policy;
- fresh terminal observation and rerun invalidation before durable publication.

### Non-authorizing positive verification seam

The sole direct-module test probe is a lazy `Effect<void>`. It requires genuine
registration and invocation capability objects, constructs a local pinned test
policy from an exact test fixture, runs the same four-read acquisition,
revalidators, and classifier against a caller-supplied test observer, and then
discards the private candidate. It never calls the issuer, inserts into the
production WeakMap, returns evidence, or creates an authority service.

This proves authentic-input binding and acquisition/policy mechanics under a
self-consistent injected observer. It does not prove GitHub origin or genuine
authority issuance. The test fixture and probe are absent from the package-root
export, and `package.json` still exports only `.`.

### Threat boundary

The closed Layer graph prevents constructor-level observer/service/policy
injection and root-package access. It assumes a trusted same-process runtime.
It does not claim resistance to code that can monkeypatch ambient
`process.env`, filesystem APIs, or `globalThis.fetch`, or import private source
files directly. Production deployment must own that process boundary.

## Verification

The code checkpoint passed:

- strict TypeScript check;
- focused current-run suite: `29/29` tests;
- full package suite: `208/208` tests in `16/16` suites;
- build and `npm pack --dry-run`;
- staged `git diff --check`;
- three independent read-only adversarial audits with no remaining blocker in
  the OPEN/non-authorizing scope.

The full command ran through bounded Proxmox scratch:

```text
cd src/hswm/effect-runtime
proxmox-scratch run hswm-effect-run-authority-v7 --timeout 7200 -- npm run verify
```

The scratch directory was removed and no long-lived worker remained. These are
engineering results only. They are not GitHub observations, an S2S numeric
result, a workflow verdict, or learned-weight evidence.

## Exact next-session order

1. Read the constitution, this handoff, the v7 KG, immutable v6, and the
   `effect-ts-functional` skill. Preserve the two protected user changes.
2. Treat `dd381f3` as the implemented code checkpoint. Do not reinterpret the
   non-authorizing probe as a current-run capability or GitHub-origin proof.
3. Replace `observeRoleArtifact(runId, headSha, role)` with fixed, no-identity
   stage operations backed by atomically consumed finite one-use permits. Each
   permit must be derived from an inspected current-run capability, bind the
   authentic stage and current numeric GitHub job ID, and make its process and
   replay limits explicit. `Context.Tag` presence alone is never authority.
4. Initialize one bounded request-ID ledger with all four current-run bracket
   IDs. Carry that same ledger atomically through permit issuance and every
   artifact metadata, download, and readback observation; reject every reuse.
5. Add the content-addressed create-only durable evidence envelope and the
   closed `register`/`confirm`/`adjudicate` stage programs. Fix executable
   entrypoints and mandatory-upload postconditions before authoring YAML. Do not
   claim cross-execution uniqueness from an in-memory Ref or WeakMap.
6. Create and independently review the exact three-job workflow bytes against
   those already closed execution surfaces, without creating preregistration.
   Pin the literal raw workflow SHA, accept the resulting contract digest,
   require the matching exact source-A manifest row, select one reviewed API
   path representation, and only then enable production current-run issuance.
   Activation must add the genuine positive Layer/issuer/inspector regression.
7. Implement the separate terminal finalizer and rerun-invalidation rule. Its
   last attempt-one observation must occur immediately before create-only
   durable publication; no earlier roster instant closes that race.
8. Independently adversarially review the full failure/VOID matrix before any
   source freeze, preregistration, future Quicknet selection, dispatch, or
   event-10 composition.

Do not create workflow bytes, preregistration, a future beacon, dispatch,
candidate, adjudication, or event 10 merely to advance engineering. Do not add
a research receipt or `F1_R8_RESULTS_LOG.md` entry for this routine control
plane work.

## Protected scope and nonclaims

These pre-existing user changes remain uncommitted and protected:

- `src/hswm/experiments/continual_live.py`
- `tests/test_hswm_continual_live.py`

No remote KG was mutated. No workflow source bytes, reviewed API path,
source-A workflow manifest binding in the real program, GitHub-origin current
run observation, genuine current-run capability, one-use stage permit, durable
external evidence envelope, preregistration, future pulse, dispatch, candidate,
adjudication, event-10 verdict, learned `W`, or outcome-bound causal update was
created.

## Minimal continuation prompt

```text
Continue HSWM from code checkpoint
dd381f341c08057356ba3e70c83fca33714094b6. Read
docs/canon/HSWM_CONSTITUTION_2026-08-20.md,
docs/operations/HSWM_SWM0W_S2S_RUN_AUTHORITY_IMPLEMENTED_NEXT_SESSION_2026-08-22.md,
ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v7.json, immutable v6, and the
effect-ts-functional skill. Preserve the two continual_live changes. Stay
strict TypeScript/Effect v3 with Python numeric-only. The authentic-input
four-read acquisition/revalidation/policy path is engineering-clear only under
a non-authorizing test observer. Production remains WORKFLOW_SOURCE_BYTES_OPEN;
no genuine current-run capability or GitHub-origin proof exists. Next define
fixed no-identity stage artifact operations, atomic finite permits, and one
bounded request-ID ledger seeded by the four bracket IDs. Carry it through all
artifact metadata/download/readback operations. Then close the durable envelope
and stage entrypoints plus mandatory-upload postconditions before authoring and
reviewing workflow YAML. Only after pinning its hash, manifest row, contract,
and API path may genuine issuance be enabled. Finish the fresh terminal
reobservation/rerun-invalidation boundary and full failure/VOID review before
source freeze or any preregistration/beacon/dispatch/event 10.
```
