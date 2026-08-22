# HSWM SWM-0W-S2S TypeScript/Effect observation implementation handoff

Date: 2026-08-22

Code checkpoint: `98f9e7c14933cad4ccccc352e94aeb904f035ade`

Checkpoint parent: `1e620fba8e8eaf147f81a95c0bf05b8553e23d9c`

Authority: the TypeScript/Effect direction is `USER_PRIMARY`; the concrete
implementation and continuation boundary are `SECONDARY_AI_PROPOSED` and have
been adversarially verified as an engineering boundary.

Status: `BLOCKED_PRE_PREREG /
OBSERVATION_REVALIDATION_ENGINEERING_CLEAR_INTERNAL_CONSISTENCY_NOT_ORIGIN /
WORKFLOW_RUNS_FOR_HEAD_ENGINEERING_CLEAR_MULTIPLICITY_PRESERVING /
WORKFLOW_SOURCE_BYTES_OPEN / CURRENT_RUN_AUTHORITY_OPEN /
SCIENTIFIC_UNJUDGED`.

This is the current continuation entrypoint. It supersedes the
[`v5 observation-authority design handoff`](HSWM_SWM0W_S2S_OBSERVATION_AUTHORITY_DESIGN_NEXT_SESSION_2026-08-22.md)
only for continuation and does not rewrite that frozen design checkpoint. Its
companion
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v6.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v6.json)
is a local repository KG projection, not HSWM cognition, a remote KG
publication, a preregistration, or scientific evidence.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
Its evolving hypergraph remains one living harness, world model, and continuous
learner. Effect services, GitHub API projections, repository documents, tests,
and ontology records are bounded interfaces and evidence instruments; they are
not separate cognition, routing, or learning subsystems.

This checkpoint advances only `Pi`:

- `H`: target identity unchanged; no topology or cognition result;
- `W`: no learned semantic macro-weight result;
- `A`: no activation or readout-efficacy result;
- `F`: no confirmatory candidate, adjudication, or function-cell result;
- `Pi`: retained GitHub observation consistency and exact head-SHA roster
  observation are now implemented and adversarially verified.

The outcome-bound causal-learning loop did not advance. Event chronology stays
structurally clear only through `1 -> 6 -> 9`; event 10 remains unauthorized.

## Runtime direction

The long-lived control runtime remains strict TypeScript-first with Effect v3:

- TypeScript `5.9.3`, Effect `3.22.1`, Node `24.13.0`;
- deterministic parsing and recomputation remain pure `Either` kernels after
  immutable snapshots;
- observable acquisition and hostile reader execution remain lazy Effects with
  typed failures;
- `Context.Tag`, private `Layer` composition, and Effect `Clock` own external
  capabilities and JSON observation time;
- Python remains an opaque deterministic numeric oracle;
- observers, transports, validators, Live Layers, and authority inspectors stay
  absent from the package-root export.

The `effect-ts-functional` skill governed version routing, laziness, typed-error,
and verification choices. It is working-method metadata, not a runtime
dependency or HSWM capability.

## What code checkpoint `98f9e7c` establishes

### Lazy standalone revalidation for run, jobs, and run roster

The private GitHub module now exposes three module-local validation boundaries:

```ts
validateS2SGitHubWorkflowRunObservation(input, expectedRunId)
validateS2SGitHubWorkflowAttemptJobsObservation(input, expectedRunId)
validateS2SGitHubWorkflowRunsForHeadObservation(input, expectedHeadSha)
```

Each returns a lazy `Effect` with one typed
`S2SGitHubObservationValidationError` family. The jobs validator fixes attempt
one. Expected run/head identity comes from the independent validator argument,
not the submitted receipt.

The common path descriptor-inspects the exact wrapper and 15-key receipt,
detaches and invokes the raw-byte reader exactly once per execution, copies one
bounded base `Uint8Array`, and recomputes the observation through the existing
pure constructor. Buffer, subclasses, typed-array Proxies, own accessors,
symbols, detached storage, oversize input, and both same-realm and cross-realm
`SharedArrayBuffer` backing are rejected through the typed Effect channel.

Receipt comparison is driven by the trusted recomputed shape. Nested objects
reject accessors, hidden/extra/symbol keys, and custom prototypes; arrays reject
holes, extras, symbols, accessors, and custom prototypes. The validator returns
only a new frozen recomputed observation with a defensive byte reader.

The fixed failure reasons are:

```text
INVALID_ARGUMENT
WRAPPER_REJECTED
RECEIPT_REJECTED
RAW_BODY_REJECTED
RAW_BODY_DRIFT
RECOMPUTATION_REJECTED
RECEIPT_SELF_HASH_MISMATCH
RECEIPT_MISMATCH
```

This proves only internal consistency of the retained bytes, projection,
provenance strings, and receipt. A caller can fabricate a fully self-consistent
request ID, ETag, timestamp, body, and receipt. Therefore this boundary does
not authenticate GitHub origin. Transparent Proxies also cannot be universally
identified by JavaScript reflection. Production origin must be established by
a private composition root that fixes the approved Live observer or consumes
an equivalent module-authentic capability.

### Exact multiplicity-preserving workflow-runs-for-head observation

The observer now owns this exact endpoint policy:

```text
/repos/gj3447/HSWM/actions/workflows/swm0w-s2s-confirmatory.yml/runs?branch=main&event=push&head_sha=<lowercase-40-hex>&per_page=100
```

The transport allowlist admits only that spelling and order. The projection
requires `total_count === workflow_runs.length <= 100`, rejects duplicate run
IDs, sorts distinct IDs ascending, deeply freezes the result, and requires each
row to match the requested head SHA plus repository and head-repository
`gj3447/HSWM`. Zero, one, and multiple rows are all valid observations.

The observer deliberately does not decide current-run uniqueness or authorize a
run. It also records syntactically valid workflow paths including an observed
`@main` suffix without turning that representation into an authority rule. The
future run-authority Layer must require exactly one row and cross-check its full
identity against authentic registration-B and current-invocation capabilities.

`S2S_CONFIRMATORY_WORKFLOW_ID` is the one internal workflow filename literal;
the existing workflow path derives from it. It was not added to
`WORKFLOW_CONTRACT_CORE`, so the canonical v1 contract hash remains
`45e14e0e3d2a0ca0b652c2d39741b264968d4ecdb2d0ff5b74eabd0aa8904050`.

All five JSON observation Live methods now obtain receipt time from Effect
`Clock`. ZIP-download receipt clock migration was outside this slice.

### Root capability containment

Regression tests keep the observer port and Live Layer, transport constructor,
new observation constructor and validators, workflow filename constant,
invocation event reader, and workflow-manifest inspector absent from the package
root. This is module containment, not GitHub-origin proof by itself.

## Verification

The implementation checkpoint passed:

- strict TypeScript check;
- focused observation/contract/artifact/public-API suite: `50/50` tests in
  `4/4` suites;
- full package suite: `179/179` tests in `15/15` suites;
- build and `npm pack --dry-run`;
- `git diff --check`;
- two independent read-only implementation audits, including a cross-realm
  shared-memory bypass discovery, repair, and re-audit.

The full verification ran through the bounded Proxmox scratch runner. This is
engineering verification only. It is not an S2S numeric result, a scientific
verdict, or evidence that GitHub emitted any particular observation.

## Exact next-session order

1. Read the constitution, this handoff, the v6 KG, the immutable v5 design, and
   the `effect-ts-functional` skill. Preserve the two protected user changes.
2. Implement a private request-distinct run-authority Layer over the bracket
   `run-start -> attempt-one jobs -> workflow-runs-for-B -> run-end`.
3. Consume authentic registration-B and current-invocation capabilities;
   require exactly one roster row and equality with the authentic invocation
   run ID, attempt one, repository/head repository, head SHA, event, branch,
   workflow identity, and an explicitly reviewed path representation.
4. Reject reused request IDs, observation identity drift, reruns, incomplete or
   unsuccessful required predecessors, wrong current job, and zero/multiple
   roster rows. Re-observe immediately before any future durable authority
   commit and define rerun invalidation policy.
5. Keep production positive issuance closed while workflow source bytes and the
   source-A manifest binding are OPEN. Any pre-workflow positive fixture remains
   sealed inside tests and absent from public exports.
6. After that gate is verified, continue with atomic finite stage permits,
   durable content-addressed external evidence, closed stage programs, reviewed
   workflow bytes, and the terminal rerun-safe finalizer.

Do not create the workflow, preregistration, future beacon, dispatch, candidate,
or event 10 merely to advance this next engineering slice. Do not add a research
receipt or `F1_R8_RESULTS_LOG.md` entry for this routine control-plane work.

## Protected scope and nonclaims

These pre-existing user changes remain uncommitted and protected:

- `src/hswm/experiments/continual_live.py`
- `tests/test_hswm_continual_live.py`

No remote KG was mutated. No workflow source bytes, source-A workflow manifest
binding, unique current-run capability, stage permit, durable external evidence
envelope, preregistration, future pulse, dispatch, candidate, adjudication,
event-10 verdict, learned `W`, or outcome-bound causal update was created.

## Minimal continuation prompt

```text
Continue HSWM from code checkpoint
98f9e7c14933cad4ccccc352e94aeb904f035ade. Read
docs/canon/HSWM_CONSTITUTION_2026-08-20.md,
docs/operations/HSWM_SWM0W_S2S_OBSERVATION_AUTHORITY_IMPLEMENTED_NEXT_SESSION_2026-08-22.md,
ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v6.json, the immutable v5
handoff, and the effect-ts-functional skill. Preserve the two continual_live
changes. Stay strict TypeScript/Effect v3 with Python numeric-only. Observation
revalidation and multiplicity-preserving workflow-runs-for-head are engineering
clear for internal consistency, not GitHub origin or unique-run authority. Next
implement the private request-distinct run-authority Layer over
run-start/jobs/runs-for-B/run-end, consuming authentic B and invocation
capabilities. Keep positive issuance closed while workflow source bytes remain
OPEN. Do not create workflow bytes, preregistration, a future pulse, dispatch,
or event 10 in that slice.
```
