# HSWM SWM-0W-S2S TypeScript/Effect observation-authority design handoff

Date: 2026-08-22

Repository parent checkpoint: `3c0d3e4cb2e0f8be562f1009ae83fecd742feb99`

Implemented code checkpoint: `5fe203815bdba2b3cdbf6d5d67f739b23c63b084`

Authority: the TypeScript/Effect direction is `USER_PRIMARY`; the concrete
validator, query, and continuation design is `SECONDARY_AI_PROPOSED` until it
is implemented and adversarially verified.

Status: `BLOCKED_PRE_PREREG / DESIGN_FROZEN_IMPLEMENTATION_OPEN /
STRUCTURAL_1_6_9_CLEAR / WORKFLOW_SOURCE_BYTES_OPEN /
TRUSTED_CURRENT_RUN_OBSERVATION_OPEN / CURRENT_RUN_AUTHORITY_OPEN /
SCIENTIFIC_UNJUDGED`.

This is the current continuation entrypoint. It supersedes the
[`invocation-authority handoff`](HSWM_SWM0W_S2S_INVOCATION_AUTHORITY_NEXT_SESSION_2026-08-22.md)
only for continuation and leaves that hash-bound engineering checkpoint
unchanged. Its companion
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v5.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v5.json)
is a local repository KG projection, not HSWM cognition, a remote KG
publication, a preregistration, or scientific evidence.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
Its evolving hypergraph remains one living harness, world model, and continuous
learner. TypeScript services, Effect Layers, GitHub observations, repository
documents, tests, and ontology records are bounded projections and interfaces;
they are not separate cognition, routing, or learning subsystems.

This checkpoint records a design decision and advances no runtime behavior:

- `H`: target identity unchanged; no topology or cognition evidence;
- `W`: no semantic macro-weight or learned-weight result;
- `A`: no activation/readout efficacy result;
- `F`: no confirmatory candidate, adjudication, or function-cell result;
- `Pi`: the next external-observation integrity boundary is specified but not
  implemented.

The outcome-bound causal-learning loop did not advance. Event chronology stays
structurally clear only through `1 -> 6 -> 9`; event 10 remains unauthorized.

## TypeScript/Effect direction is active

The long-lived control runtime remains strict TypeScript-first with Effect v3:

- TypeScript `5.9.3`, Effect `3.22.1`, Node `24.13.0`;
- pure constructors and post-snapshot recomputation kernels return typed
  values or typed failures; validators remain lazy Effect boundaries;
- `Context.Tag` services and `Layer` composition own acquisition and authority;
- Effect `Clock` supplies observable time in live services;
- immutable snapshots cross every `unknown` and external-I/O boundary;
- Python stays an opaque deterministic numeric oracle for generation,
  fit/replay, evaluation, and canonical numeric bytes;
- privileged adapters, validators, issuers, inspectors, Live Layers, and test
  Layers stay absent from the package-root export.

The design audit used the repository's `effect-ts-functional` skill and its
Effect v3 version-routing and verification rules. This is working-method
metadata, not a runtime dependency or an HSWM capability. No package-local
`node_modules/effect/AGENTS.md` override was present at this checkpoint.

## Current evidence boundary

The existing private GitHub module already has pure constructors for one
workflow run, one attempt's jobs, run artifacts, and one artifact. Each
constructor parses bounded duplicate-aware JSON, projects strict fields, binds
GitHub response provenance, hashes raw bytes and projections, and returns a
defensive raw-body reader. The Live observer uses an exact transport allowlist.

That is not yet sufficient for authority. `S2SGitHubObserver` is a replaceable
Effect service, so a caller-provided Layer can return an arbitrary structurally
plausible wrapper. No standalone boundary currently reparses the retained bytes
and proves that the receipt equals the pure constructor's recomputation.

Even the planned validator is designed to establish only byte/receipt internal
consistency.
It cannot prove that a request ID, ETag, response time, or raw body actually came
from GitHub: an attacker can fabricate a completely self-consistent observation.
Production origin therefore also requires a private composition root that fixes
the approved Live observer (or an equivalent module-authentic capability). A
standalone validator must never be described as GitHub-origin authentication.

## Frozen next-slice contract A: standalone observation revalidation

Implement these internal lazy Effect entrypoints first:

```ts
validateS2SGitHubWorkflowRunObservation(input, expectedRunId)
validateS2SGitHubWorkflowAttemptJobsObservation(input, expectedRunId)
validateS2SGitHubWorkflowRunsForHeadObservation(input, expectedHeadSha)
```

They should return `Effect.Effect<TrustedObservation,
S2SGitHubObservationValidationError>` with no service requirement. Calling an
untrusted `readRawBody` function is observable work, so constructing a validator
Effect must not execute it eagerly. Capture descriptor inspection and the one
reader call lazily with `Effect.try`, then pass the immutable snapshot to a pure
recomputation kernel that uses the existing `Either` constructors. The jobs
entrypoint must hard-code attempt `1` rather than accept caller-selected attempt
identity.

The common validator algorithm is exact:

1. Validate the expected run ID as a positive safe integer, or the expected
   head SHA as exactly 40 lowercase hexadecimal characters.
2. Descriptor-inspect one plain/null-prototype wrapper with exactly two
   enumerable data properties: `receipt` and `readRawBody`. Reject symbols,
   hidden/extra properties, accessors, custom prototypes, and throwing or
   incompatible reflection traps. JavaScript cannot generally identify every
   transparent Proxy, so do not claim universal Proxy detection.
3. Descriptor-inspect the receipt as exactly these 15 enumerable data
   properties: `schemaVersion`, `kind`, `apiVersion`, `repository`,
   `endpointPathAndQuery`, `observedAtUnixSeconds`, `httpStatus`,
   `githubRequestId`, `githubApiVersionSelected`, `responseEtag`,
   `rawBodyByteLength`, `rawBodySha256`, `projection`, `projectionSha256`, and
   `receiptSha256`.
4. Call `readRawBody` exactly once, detached from the caller object. Immediately
   snapshot one unshared base `Uint8Array` no larger than 8 MiB. Reject Buffer,
   subclasses, `SharedArrayBuffer`, incompatible typed-array Proxies, symbols,
   detached storage, own `buffer`/`byteLength` descriptors, and every throwing
   trap. Submitted JavaScript property getters are never invoked; reflection
   traps are caught.
5. Compare the snapshot length and SHA-256 with the receipt before parsing.
6. Copy only the receipt's descriptor-proven timestamp and three response
   provenance fields into the existing pure constructor. Supply expected
   run/head identity independently; do not recover it from the caller receipt.
7. Reparse the single raw snapshot and recompute projection, projection hash,
   endpoint, kind, schema, provenance binding, and receipt self-hash with the
   appropriate pure constructor.
8. Compare the submitted `receiptSha256` with the recomputed receipt self-hash;
   report that failure separately from other receipt drift.
9. Compare the submitted receipt with the recomputed receipt using a bounded
   exact deep-data comparator driven by the trusted recomputed shape. At every
   object depth reject extras, hidden keys, symbols, accessors, and custom
   prototypes. Arrays must have exactly indices `0..length-1` plus the normal
   non-enumerable own `length`, with no holes, symbols, accessors, or extra
   properties. Compare primitives with `Object.is`.
10. Return only the recomputed frozen observation and its defensive byte reader,
   never the caller's object.

One `Data.TaggedError` is sufficient with fixed reasons:

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

Every reflection and reader call must be captured by the lazy Effect boundary;
expected hostility must fail through the typed error channel rather than become
an Effect defect. Error details must not echo attacker-controlled values.

## Frozen next-slice contract B: workflow runs for exact head SHA

Add the exact private observation endpoint:

```text
/repos/gj3447/HSWM/actions/workflows/swm0w-s2s-confirmatory.yml/runs?branch=main&event=push&head_sha=<lowercase-40-hex>&per_page=100
```

The query order, lowercase SHA spelling, omitted `page=1`, and one-page closure
are local strict receipt policy. They are not GitHub guarantees. GitHub's API
supports a workflow filename as `workflow_id`, the `branch`, `event`, and
`head_sha` filters, and `per_page` up to 100; it can still return multiple runs.

Add one additive v2 observation kind, `WORKFLOW_RUNS_FOR_HEAD`, and one deeply
frozen projection:

```ts
interface S2SGitHubWorkflowRunsProjection {
  readonly totalCount: number
  readonly workflowRuns: ReadonlyArray<S2SGitHubWorkflowRunProjection>
}
```

Keep observation receipt schema v2 because its envelope and hash fields do not
change. Refactor the existing run parser to accept a diagnostic path, then parse
`total_count` and `workflow_runs` with these invariants:

- `total_count` is a nonnegative safe integer;
- `total_count === workflow_runs.length <= 100`;
- every row has the requested head SHA and exact `repository/headRepository`
  identity `gj3447/HSWM`;
- distinct run IDs are sorted ascending after duplicate-ID rejection;
- every row, array, and projection is frozen;
- zero, one, or multiple distinct rows are all valid observations.

The observer records what GitHub returned. It must not silently turn a
multiplicity policy into parser behavior. The later run-authority layer—not the
observer—must require exactly one row and cross-check it against the authentic
current invocation, attempt one, workflow identity, event/ref, and acquisition
bracket.

Derive the workflow filename from the internal literal
`S2S_CONFIRMATORY_WORKFLOW_ID = "swm0w-s2s-confirmatory.yml"` without adding a
redundant field to `WORKFLOW_CONTRACT_CORE`; that preserves the existing
canonical v1 contract hash. Migrate all JSON observation Live methods—the
existing run, jobs, artifacts, and artifact methods plus the new list method—to
Effect `Clock` rather than `Date.now()`. The ZIP-download receipt clock migration
is outside this slice.

Official GitHub examples can represent a workflow-run `path` as
`.github/workflows/<file>.yml@main`. Do not copy the current generic artifact
boundary's unsuffixed-only equality into run authority. Define and test one
explicit acceptable representation only after the live semantics are pinned;
until then, production authority remains fail-closed on ambiguity.

Official references:

- [Workflow runs REST API](https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28)
- [REST API pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api?apiVersion=2022-11-28)
- [REST API versions](https://docs.github.com/en/rest/about-the-rest-api/api-versions)

## Frozen next-slice contract C: acquisition and authority separation

After all three observations pass standalone recomputation, the future private
run-authority Layer must acquire this request-distinct bracket:

```text
run-start -> attempt-one jobs -> workflow-runs-for-B -> run-end
```

It must reject reused GitHub request IDs, run identity drift, a non-completed or
unsuccessful required predecessor, wrong current job, reruns, zero or multiple
matching runs, and a sole run whose ID differs from the current invocation.
The complete workflow name, event, branch, repository, head repository, SHA,
attempt, and reviewed path representation remain authority checks.

The Layer must consume the authentic registration-B and current-invocation
capabilities. Its production constructor must refuse every positive issuance
while the workflow-source byte status is OPEN. A test-only positive fixture must
stay sealed inside the test module and absent from public exports.

## Adversarial verification matrix

The validator tests must cover valid run/jobs/list recomputation, a reader called
exactly once, independent returned objects and defensive bytes, and every
following hostile family:

- wrapper/receipt missing, extra, hidden, symbol, accessor, custom prototype,
  and throwing or incompatible Proxy cases, without claiming all transparent
  Proxies are detectable;
- nested projection/job/label accessor, symbol, extra key, array hole, and extra
  array-property cases;
- reader throw, Buffer, typed-array subclass, shared backing storage,
  incompatible typed-array Proxy, own `buffer` or `byteLength` accessor,
  detached or oversized bytes;
- raw length/hash drift, malformed provenance, selected API-version or ETag
  drift, request-ID tampering, projection tampering even with recomputed caller
  hashes, wrong observation kind, and wrong expected run/head identity;
- the invariant that hostile `unknown` input fails in the typed Effect channel
  rather than throwing or becoming a defect.

The list tests must cover 0/1/2 rows, deterministic sorting and freezing,
duplicate IDs, total-count mismatch, more than 100 rows, head/repository drift,
noncanonical requested SHA, exact endpoint/provenance, and rejection of
reordered, extra, percent-encoded, or uppercase-SHA transport paths.

Adding the Observer method requires updating exactly two current observer mocks
in `s2s-live-artifact.test.ts`. Root API regression tests must explicitly keep
the new constructor, validators, workflow filename constant, invocation event
reader, workflow-row inspector, observer port, and Live Layer private.

## Exact next-session order

1. Read the constitution, this handoff, the v5 KG, and the Effect skill. Preserve
   the two protected user changes below.
2. Implement the exact wrapper/receipt/byte snapshot helpers and the run/jobs
   validators as lazy Effects with one typed error family; keep only the
   post-snapshot recomputation kernel pure and `Either`-based.
3. Implement the workflow filename derivation, runs-for-head projection,
   parser, constructor, observer method, exact transport allowlist, and Live
   Effect-Clock acquisition.
4. Implement the runs-for-head validator through the same recomputation path.
5. Add the full hostile-input, multiplicity, endpoint, mock, and public-export
   regression matrix. Run focused tests, strict check, full `npm run verify`, and
   an independent diff audit.
6. Only after those boundaries are green, implement the separate private
   run-authority Layer and its request-distinct bracket. Keep production positive
   issuance closed while workflow source bytes remain OPEN.
7. Continue with atomic finite stage permits, durable evidence envelope, closed
   stage programs, reviewed workflow bytes, and the terminal finalizer in the
   order recorded by v4.

Do not create the workflow file, preregistration, future beacon, dispatch, or
event 10 in the observation-revalidation slice. Do not add a research receipt or
`F1_R8_RESULTS_LOG.md` entry for this routine control-plane work.

## Verification and protected scope

No implementation file changed in this design-only checkpoint. Its baseline is
the already verified code commit `5fe2038`: strict TypeScript, `167/167` Vitest
tests in `15/15` suites, build, and pack dry-run passed there. This handoff's KG
closure tests are documentation integrity checks, not runtime verification or
a learned S2S efficacy verdict.

These pre-existing user changes remain protected and must not be staged or
modified:

- `src/hswm/experiments/continual_live.py`
- `tests/test_hswm_continual_live.py`

No remote KG was mutated. No confirmatory workflow, preregistration, future
pulse, dispatch, candidate, adjudication, event-10 verdict, learned `W`, or
outcome-bound causal update was created.

## Minimal continuation prompt

```text
Continue HSWM from the commit containing this handoff. Its repository parent is
3c0d3e4cb2e0f8be562f1009ae83fecd742feb99 and its implemented code checkpoint is
5fe203815bdba2b3cdbf6d5d67f739b23c63b084. Read
docs/canon/HSWM_CONSTITUTION_2026-08-20.md,
docs/operations/HSWM_SWM0W_S2S_OBSERVATION_AUTHORITY_DESIGN_NEXT_SESSION_2026-08-22.md,
ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v5.json, and the
effect-ts-functional skill. Preserve the two continual_live changes. Stay strict
TypeScript/Effect v3 with Python numeric-only. First implement lazy standalone
run/jobs observation revalidation with a pure post-snapshot recomputation core,
then the exact bounded workflow-runs-for-head observation and validator, with
the full adversarial matrix and private root API.
Next implement a request-distinct run-authority Layer that consumes authentic B
and invocation capabilities but fails closed while workflow source bytes are
OPEN. Do not author the workflow, create preregistration, select a future pulse,
dispatch, or compose event 10 in this slice.
```
