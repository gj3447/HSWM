# HSWM SWM-0W-S2S TypeScript/Effect invocation-authority handoff

Date: 2026-08-22

Code checkpoint: `5fe203815bdba2b3cdbf6d5d67f739b23c63b084`

Checkpoint parent: `7f2754b5a60651893aed6501636ee732ffc5634c`

Authority: the TypeScript/Effect direction is `USER_PRIMARY`; this concrete
contract, capability, and continuation design is `SECONDARY_AI_PROPOSED`.

Status: `BLOCKED_PRE_PREREG / STRUCTURAL_1_6_9_CLEAR /
WORKFLOW_IDENTITY_AND_STAGE_CONTRACT_V1_CLEAR /
CURRENT_INVOCATION_AUTHORITY_CLEAR_PROCESS_LOCAL /
WORKFLOW_SOURCE_BYTES_OPEN / CURRENT_RUN_AUTHORITY_OPEN /
SCIENTIFIC_UNJUDGED`.

This is the current continuation entrypoint. It supersedes the prior authority
handoff only for continuation and does not rewrite its historical claims. The
companion
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v4.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v4.json)
is a local repository KG projection. It is not HSWM cognition, a remote KG
publication, a preregistration, or a scientific result.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
Its evolving hypergraph remains simultaneously the living harness, world
model, and continuous learner. Effect services, GitHub, repository files, and
ontology records are bounded projections and interfaces rather than separate
cognitive subsystems.

This checkpoint advances only `Π`:

- `H`: target identity unchanged; no new cognition/substrate evidence;
- `W`: no learned semantic-weight result;
- `A`: no activation or readout-efficacy result;
- `F`: no valid confirmatory candidate or adjudication execution;
- `Π`: one pure workflow identity/stage contract and one strict,
  process-local current-invocation authority are now implemented.

The outcome-bound causal-learning loop did not advance. Event chronology
remains structurally clear only through `1 -> 6 -> 9`; no trusted path appends
event 10, exposes a verdict, updates learned `W`, or authorizes a future
measurement.

## Runtime direction

- Strict TypeScript `5.9.3`, Effect `3.22.1`, Node `24.13.0`.
- Effect v3 `Schema`, `Context.Tag`, `Layer`, typed
  `Data.TaggedError`, immutable snapshots, and explicit requirements remain
  the runtime idiom.
- TypeScript owns control chronology, authority, external observation,
  evidence envelopes, and workflow composition.
- Python remains an opaque deterministic numeric oracle for generation,
  fit/replay/evaluation, and canonical candidate/adjudication bytes.
- Privileged adapters, issuers, inspectors, live Layers, and test Layers remain
  absent from the package-root export.

## What code checkpoint `5fe2038` establishes

### Pure workflow identity and stage contract v1

`s2s-workflow-contract.ts` is now the internal single source for:

- repository `gj3447/HSWM`;
- event/ref/branch `push / refs/heads/main / main`;
- workflow name `SWM-0W-S2S confirmatory`;
- workflow path
  `.github/workflows/swm0w-s2s-confirmatory.yml`;
- workflow ref
  `gj3447/HSWM/.github/workflows/swm0w-s2s-confirmatory.yml@refs/heads/main`;
- preregistration trigger
  `prereg/PREREG_SWM0W_S2S_GATE_V1.json`;
- exactly run attempt `1`.

The stage graph is exact:

| stage | job ID/name | produces | consumes |
|---|---|---|---|
| `REGISTER` | `register` | `REGISTRATION` | none |
| `CONFIRM` | `confirm` | `CANDIDATE` | `REGISTRATION` |
| `ADJUDICATE` | `adjudicate` | `ADJUDICATION` | `REGISTRATION`, `CANDIDATE` |

The contract also declares four ordered, one-use artifact read operations:

1. `CONFIRM_READ_REGISTRATION`;
2. `ADJUDICATE_READ_REGISTRATION`;
3. `ADJUDICATE_READ_CANDIDATE_FIRST`;
4. `ADJUDICATE_REREAD_CANDIDATE`.

The deeply frozen v1 contract hash is:

`45e14e0e3d2a0ca0b652c2d39741b264968d4ecdb2d0ff5b74eabd0aa8904050`

This hash deliberately covers
`OPEN_UNTIL_WORKFLOW_BYTES_EXIST`. It is not a workflow-file hash. The
workflow file is absent at this checkpoint, so no run/stage authority may be
issued from this contract version.

### Strict current-invocation evidence and authority v1

`s2s-invocation.ts` accepts exactly 18 enumerable string data properties:

`GITHUB_ACTIONS`, `GITHUB_API_URL`, `GITHUB_EVENT_NAME`,
`GITHUB_JOB`, `GITHUB_REF`, `GITHUB_REF_NAME`, `GITHUB_REF_TYPE`,
`GITHUB_REPOSITORY`, `GITHUB_RUN_ATTEMPT`, `GITHUB_RUN_ID`,
`GITHUB_SERVER_URL`, `GITHUB_SHA`, `GITHUB_WORKFLOW`,
`GITHUB_WORKFLOW_REF`, `GITHUB_WORKFLOW_SHA`, `RUNNER_ARCH`,
`RUNNER_ENVIRONMENT`, and `RUNNER_OS`.

It rejects missing or excess properties, symbols, accessors, custom
prototypes, hostile Proxies, noncanonical run IDs, reruns, wrong jobs,
repository/ref/workflow drift, and non-Linux/X64 GitHub-hosted runners.

The raw push-event boundary uses fatal UTF-8 and duplicate-aware bounded JSON.
It requires one non-forced, non-created, non-deleted main-branch push with
exactly one distinct commit; `before != after`; and
`after == GITHUB_SHA == GITHUB_WORKFLOW_SHA == commits[0].id ==
head_commit.id`. The receipt uses neutral `pushBeforeSha` and
`pushAfterSha` names. Only a future run authority may identify them as
source A and registration B after authentic capability cross-checks.

Evidence
`hswm-swm0w-s2s-current-invocation-evidence/v1` binds:

- the workflow-contract schema and canonical hash;
- run ID, attempt, exact job ID, derived stage, and workflow path;
- capture time;
- immutable environment and event projections plus their hashes;
- exact event byte length and raw SHA-256;
- one receipt self-hash over every preceding evidence field.

A module-private `WeakMap` authenticates the process-local capability. Raw
event bytes remain privately retained and inspectors return defensive copies.
A structurally equal or rehashed object is not authority.

The live Layer treats `GITHUB_EVENT_PATH` as acquisition-only. It requires
one bounded absolute path, opens with `O_NOFOLLOW`, accepts only a regular
file of 2..1,048,576 bytes, reads one exact snapshot, and compares final
identity, size, mode, mtime, and ctime before issuance. Capture time comes from
Effect `Clock`.

### Conditional source-workflow-row inspector

The authentic registration-B capability now retains a private projection of
the exact source-A tracked-byte manifest row for the workflow path. Inspection
succeeds only for exactly one `100644/blob` row and returns the raw
workflow-file SHA plus whole tracked-manifest SHA.

This is an implemented fail-closed inspector, not an actual workflow binding.
B authority can still authenticate preregistration lineage when the workflow
row is absent, while the separate workflow-row inspection fails typed. A
future run-authority Layer must require successful inspection and equality to
the reviewed literal workflow-file hash.

### Centralized identity without a public authority leak

The existing preregistration, GitHub, and artifact modules now reuse the
workflow-contract repository/ref/event/workflow/job/artifact constants. Root
API regression tests keep the contract, current-invocation service/live Layer,
inspectors, validators, and test Layer private.

### Historical KG hash closure

The v1 and v3 KG records remain unchanged. Their regression tests now accept a
current-path hash change only when one unique continuation chain reaches a
later KG artifact binding for those exact current bytes. This preserves
historical hashes while preventing ordinary successor implementation from
being misreported as mutation of the historical checkpoint.

## Exact source anchors

| path | SHA-256 | role |
|---|---|---|
| `src/hswm/effect-runtime/src/s2s-workflow-contract.ts` | `b31370d476234ece1148a53531b11cfd01d9cefe9624541031db2227afe91a50` | internal workflow identity/stage/read-operation contract |
| `src/hswm/effect-runtime/src/s2s-invocation.ts` | `73ececd3050515928cdc42aa1c8919ae79fadc7855fc31cada7eacee96f618a0` | strict current-invocation receipt and capability |
| `src/hswm/effect-runtime/src/s2s-preregistration.ts` | `9c645535295a7a1842f175fdfbb40e7cbd103b54ec9d617833e5eecf13a224e3` | registration-B authority and conditional workflow-row binding |
| `src/hswm/effect-runtime/test/s2s-workflow-contract.test.ts` | `0d93caec7b01ced0ebae7c2859429a6cae6c0f702f66642f665f6d823e8578a9` | contract order, role, freeze, and fixed digest regressions |
| `src/hswm/effect-runtime/test/s2s-invocation.test.ts` | `311c9d1672535b216bbbf4395a282ecbb5ed16c7f34cc2517b75ce019e1ec8a3` | invocation identity, tamper, capability, and live-file regressions |

These are engineering source anchors, not a material-research receipt. This
routine control-plane work does not add a content-addressed research receipt or
an `F1_R8_RESULTS_LOG.md` entry.

## Remaining P0 gates

1. **Workflow source bytes and manifest binding are open.** The exact workflow
   file does not exist. Its reviewed bytes must be committed without a
   preregistration, hash-pinned in the contract, and later appear as exactly
   one `100644/blob` source-A manifest row.
2. **Replaceable observation Layers are not independently revalidated.**
   Before observation values can mint authority, a standalone validator must
   snapshot the wrapper and raw-body getter, reparse with the pure
   constructors, recompute every projection/self-hash, and return the trusted
   recomputation.
3. **Unique current-run evidence is absent.** Attempt one alone does not rule
   out reset-and-repush duplicate runs. Add the exact bounded query
   `/repos/gj3447/HSWM/actions/workflows/swm0w-s2s-confirmatory.yml/runs?branch=main&event=push&head_sha=<B>&per_page=100`
   and require exactly one matching run.
4. **Run/stage capability issuance is absent.** No Layer yet combines an
   authentic B capability, authentic current invocation, exact reviewed
   workflow row/hash, and fresh request-distinct GitHub observations.
5. **The generic artifact boundary remains open.**
   `observeRoleArtifact(runId, headSha, role)` still accepts caller-selected
   identity. It must be replaced by no-argument stage-specific operations
   backed by atomically consumed one-use permits.
6. **Durable envelope, composition, workflow, and finalizer remain open.** No
   create-only external evidence envelope, closed job programs, mandatory
   upload postconditions, terminal rerun-safe finalizer, complete VOID matrix,
   or event-10 authority exists.

Three empty artifact observations remain
`RECONCILED_ABSENCE_NOT_PROOF`. A finalizer must make the last attempt-one
observation immediately before create-only publication; no earlier adapter
check can close the terminal rerun race.

## Exact next-session order

1. Read the constitution, this handoff, and the v4 KG. Preserve the two
   protected user changes below.
2. Add standalone validators for workflow-run and attempt-jobs observations,
   then add the bounded workflow-runs-for-head observation and validator. Use
   only official GitHub endpoint semantics.
3. Establish the request-distinct acquisition bracket:
   `run-start -> attempt-one jobs -> exact workflow-runs-for-B list ->
   run-end`. Reject any reused request ID, identity drift, non-attempt-one
   state, zero/multiple matching runs, wrong current job, or unsuccessful
   predecessor.
4. Implement the `s2s-run-authority.ts` core as one internal Layer. It must
   consume authentic registration-B and invocation capabilities plus
   validated fresh GitHub observations, but the production Layer must refuse
   every issuance while the workflow-source status remains OPEN. Any positive
   pre-workflow test authority must be test-only, sealed, and absent from the
   root export.
5. Replace the raw artifact triple with fixed stage methods and atomically
   consumed finite permits. Share one bounded request-ID ledger through
   issuance and every metadata/download/readback operation.
6. Add the content-addressed durable evidence envelope and closed
   `register`/`confirm`/`adjudicate` stage programs. Fix the executable
   entrypoints and mandatory-upload postconditions before authoring YAML.
7. Create and independently review the exact three-job workflow bytes against
   those closed execution surfaces, without creating the preregistration file.
   Commit the workflow, replace the typed OPEN status with its literal raw-file
   SHA, accept the necessarily new contract digest, require the matching
   source-A manifest row, and only then enable production run-authority
   issuance.
8. Implement the separate terminal finalizer with its last attempt-one check
   immediately before create-only publication.
9. Independently adversarially review the full failure/VOID matrix before any
   source freeze, preregistration, future Quicknet selection, dispatch, or
   event-10 composition.

GitHub variable/context, push-payload, and workflow-run API semantics should be
checked against the official
[`Variables`](https://docs.github.com/en/actions/reference/workflows-and-actions/variables),
[`Contexts`](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts),
[`push webhook`](https://docs.github.com/en/webhooks/webhook-events-and-payloads#push),
and
[`workflow runs API`](https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28)
documentation.

## Verification

```sh
cd src/hswm/effect-runtime
npm run verify
```

Result at code checkpoint `5fe2038`: strict TypeScript passed, `167/167`
Vitest tests across `15/15` suites passed, production build passed, and npm
pack dry-run passed. Focused independent review found no commit blocker in this
slice. Tests are engineering evidence instruments, not a learned S2S efficacy
verdict.

## Protected scope and nonclaims

These pre-existing user changes were not staged or modified:

- `src/hswm/experiments/continual_live.py`
- `tests/test_hswm_continual_live.py`

No confirmatory workflow file was created, no future round was selected, no
preregistration was created, no confirmatory workflow was dispatched, no
candidate or adjudication result was produced, no event-10 verdict was
composed, no learned `W` changed, and no remote KG was mutated.

## Minimal continuation prompt

```text
Continue HSWM from code checkpoint
5fe203815bdba2b3cdbf6d5d67f739b23c63b084. Read
docs/canon/HSWM_CONSTITUTION_2026-08-20.md,
docs/operations/HSWM_SWM0W_S2S_INVOCATION_AUTHORITY_NEXT_SESSION_2026-08-22.md,
and ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v4.json. Preserve the two
protected continual_live changes. Stay strict TypeScript/Effect v3 with Python
numeric-only. First implement standalone GitHub observation revalidation and
the exact workflow-runs-for-head uniqueness query/bracket. Next implement a
run-authority core whose production Layer fails closed while workflow source
status is OPEN, replace caller-selected run/head/role with atomic finite
stage-specific permits, and close the durable stage programs and upload
postconditions. Only then author/review the exact workflow bytes, pin the
literal workflow-file hash, and enable production issuance. Keep the terminal
finalizer separate. Do not create preregistration B, select a future pulse,
dispatch, or compose event 10 before all gates clear.
```
