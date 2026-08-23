# HSWM Effect runtime

This private package is the TypeScript/Effect production-runtime seed for
HSWM. It currently implements one narrow, engineering-only transaction:
crediting an already eligible trajectory against an existing role-aware
hyperedge and registered function cell.

The boundary is intentionally small:

- `domain.ts` is a deterministic, side-effect-free `H/W/A/F` transition.
- `schema.ts` decodes unknown input and snapshots accepted values.
- `runtime.ts` supplies the Effect shell: a capability-service port, typed
  failures, Layers, and one atomic state-plus-journal transaction.
- the existing Python/NumPy SWM experiments remain research/reference oracles;
  they are not silently relabeled as this runtime.

The SWM-0W-S2S confirmatory control slice is also present, but remains
pre-dispatch engineering:

- `s2s-confirmatory.ts` freezes the pilot-adoption binding, integer resource
  policy, exact seed contract, closed monotone phases, seven VOID reasons, and
  the permanently disabled DS-derived compact-competitive phrase.
- `s2s-orchestration.ts` defines typed Effect ports for the Python numeric-only
  oracle, verified pulse source, artifact readback, and durable run evidence.
  It performs no beacon, GitHub, or numeric run.
- `s2s-durable.ts` and `s2s-durable-file.ts` implement exact predecessor-linked
  carrier recovery and a private POSIX create-only journal store. This is
  durable local control state, not GitHub observation authority. Byte-equal
  retries must re-establish directory durability before reporting success.
- `s2s-bounded-process.ts` supplies the shell-free, process-group-bounded runner.
  `s2s-live-python.ts` rehashes and invokes an open executable FD, preserves the
  reviewed venv path as `argv0`, owns a private scoped bytecode-cache root, and
  exposes fixed `confirm` and `adjudicate` operations over an exact ten-file
  source closure. `s2s-python-evidence.ts` binds the executor request, runtime,
  source identity, invocation, and exact output bytes without reserializing the
  Python receipt tree. Golden and invalid-input paths are exercised; no valid
  confirmatory candidate has been run.
- `s2s-json.ts` supplies bounded duplicate-aware integer-only JSON decoding.
  `s2s-live-github.ts` implements a read-only, exact-endpoint GitHub observer
  with bounded transport, strict projections, immutable raw-body/download
  snapshots, and request-distinct self-hashed observation receipts. Metadata
  receipts require and bind GitHub's request ID, selected API version, and
  ETag; download receipts separately bind the API redirect and signed-object
  response provenance. `s2s-live-artifact.ts` derives process-local,
  single-module producer/artifact authority, rejects reused request IDs,
  rechecks workflow-attempt identity around lookup and readback, and retains the
  complete receipt objects needed by a later durable envelope. Three
  empty-list observations produce only an explicitly non-probative
  reconciled-absence record.
- The GitHub module also implements lazy standalone run, attempt-one jobs, and
  workflow-runs-for-head revalidation. It snapshots retained bytes once,
  recomputes through the pure constructors, exact-compares nested data, and
  returns only frozen reconstructed observations. The exact head-SHA endpoint
  preserves zero, one, or multiple rows; it does not decide unique-run
  authority. These validators prove internal receipt consistency, not GitHub
  origin. The dormant current-run production graph now fixes the private Live
  observer, but it has not executed while workflow source bytes remain OPEN.
- `s2s-run-authority.ts` now binds authentic registration-B and Live invocation
  capabilities, then defines the exact request-distinct bracket
  `run-start -> jobs -> runs-for-B -> run-end`, immediate byte revalidation,
  unique-roster and fixed-stage/job policy, a self-hashed process-local
  stage-entry capability shape, and a closed Live Layer graph. A root-private
  non-authorizing `Effect<void>` probe verifies the shared acquisition/policy
  path under an injected observer but cannot call the issuer. Production exits
  with `WORKFLOW_SOURCE_BYTES_OPEN` before GitHub configuration or calls, so no
  current-run capability or GitHub-origin observation has been issued.
- `s2s-stage-artifact-permits.ts` derives the fixed stage-read identity from the
  exact current-run bearer, atomically spends finite ordered permits, and carries
  all four bracket receipts into one bounded non-evicting request/receipt
  ledger. `s2s-live-artifact.ts` exposes only lazy zero-identity stage Effects
  and independently rereads the candidate. Successful first-, second-, and
  third-poll lookup now retains the exact initial run, jobs, and every
  artifacts/run pair in one frozen trace capped at eight 1 MiB raw bodies. A
  root-private combined Layer shares one current-run service node with replay
  and fixed reads within one build, while the legacy read-only Layer signature
  remains unchanged. The one-use claim is limited to one trusted process/module
  identity slot; it is not Layer-lifetime or durable replay prevention, and the
  production graph remains dormant while workflow bytes are OPEN.
- `s2s-stage-artifact-read-replay-contract.ts` and
  `s2s-stage-artifact-read-replay.ts` implement the root-private bounded
  structural stage-read replay core. It writes one deterministic stored ZIP
  containing canonical `manifest.json` and the exact concatenated
  `observations.bin`, capped at 12,583,176 bytes, while content-addressing and
  revalidating the already durable predecessor archive instead of duplicating
  up to 64 MiB. The strict unknown-input core returns `Either`; lazy typed
  wrappers use `Effect.suspend`. Source envelopes, claims, archive bytes,
  observation receipts, permits, and candidate FIRST/REREAD ledger continuity
  are independently revalidated. Builders accept only module-issued validated
  reads. File-store recoveries are now process-locally branded, and the selected
  predecessor attachment is copied and read exactly once before producer
  self-validation reuses that inert snapshot.
- `s2s-stage-read-replay-durable-profile.ts` is the root-private local
  create-only bridge for the four reserved success-profile replay slots. It
  exact-binds current-run and predecessor evidence, fully validates every
  carrier and the candidate FIRST/REREAD pair before one non-retried commit,
  then checks the recovered predecessor prefix, latest manifest and claim, and
  replay bytes against the prevalidated snapshots. A non-authorizing fixture
  now exercises one local `REGISTER -> CONFIRM -> ADJUDICATE` chain, byte-equal
  duplicate recovery, fresh-Layer recovery, wrong-predecessor and
  swapped-operation rejection, and lazy hostile-root rejection. This does not
  validate the other profile attachments, implement a closed stage program,
  establish external durability or GitHub origin, or emit production evidence.
- `s2s-preregistration.ts` keeps the validated preregistration and direct-child
  registration-commit lineage runtime-authentic. Commit-B validation now
  returns a module-issued, WeakMap-backed capability with self-hashed immutable
  evidence instead of degrading the verified lineage back to a caller-usable
  SHA string. The current-run acquisition and policy implementation is present,
  but production issuance and dispatch authority remain closed.
- `s2s-live-drand.ts` verifies only a preregistered Quicknet round through the
  pinned local helper. `s2s-live-drand-http.ts` can fetch only that exact
  chain-specific historical/committed URL with one bounded unauthenticated GET;
  it has no `latest`, selection, retry, or fallback path.
- `s2s-zip.ts` validates one exact stored-entry GitHub Actions artifact dialect.
  `s2s-job-sequence.ts` composes isolated registration, candidate, and
  adjudication carriers at event counts `1 -> 6 -> 9`.
- Python-owned `numeric_candidate.json` and `numeric_adjudication.json` remain
  opaque canonical bytes. TypeScript hashes them raw and reads only a strict,
  hash-bound adjudication projection; it never co-authors their receipt tree.
  The candidate phase therefore binds only the raw candidate and confirm-request
  hashes. Its Python receipt is admitted later from adjudication output, after
  the Python replay has validated the candidate's canonical self-receipt.
- the `Ref` control-plane Layer is test-only, intra-process simulation. Three
  GitHub jobs must reconstruct state from immutable predecessor-linked bytes
  and fresh API/download readback; the Layer is not durable truth and does not
  imply exactly-once external effects.
- no composition function appends event 10 or exposes a verdict. That path
  remains closed until the Effect shell directly owns the real Python replay,
  independent GitHub observations, and post-job artifact readback.

This is a `Π` control/evidence boundary around the Python numeric oracle, not a
new learned `W`, an S2S efficacy result, or authorization to dispatch the
future-seeded gate. Raw transition, store, adapter, and generic-submit
capabilities are intentionally absent from the package root export until a
production orchestrator owns all provenance checks end to end.

Independent exact-byte reviews drove repairs across the source-A/B, pulse,
resource-accounting, artifact-size, journal, process, ZIP, and structural
carrier boundaries, with regression coverage on the resulting bytes. The slice
remains `BLOCKED_PRE_PREREG`: the bounded adapters and closed current-run Layer
graph are present, but no issued current-run/dispatch authority, workflow,
complete replay-closed durable evidence deployment, or external event-10
finalizer exists. Resume from the repository
[`current assertion-shell implementation handoff`](../../../docs/operations/HSWM_SWM0W_S2S_ASSERTION_SHELL_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and its
[`v21 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v21.json).

One deeply frozen, root-private `S2S_STAGE_ARTIFACT_SPECS` value now owns the
fixed REGISTER, CONFIRM, and ADJUDICATE artifact mappings used by live
predecessor reads and replay source references. Stage-specific literals remain
correlated in TypeScript. The production-intended upload-postcondition
representation and byte-budget skeleton also separates its exact
12,583,176-byte carrier ceiling from the 16 MiB profile slot. At code checkpoint
`1f45f4b`, the root-private postcondition core adds exact correlated Effect
schemas, a canonical 37-key self-receipted manifest, deterministic two-member
stored-ZIP build/validation, retained raw-observation reconstruction, and
download/archive/prepared-member cross-binding. Builders accept only
`TEST_ONLY_NON_AUTHORIZING` permit evidence; structural recovery remains
explicitly non-authorizing even when it rechecks a serialized trusted scope.
The 19 focused tests and 310 full package tests close only this strict
codec/reconstruction falsification gate.

At code checkpoint `36b4c9b`, `s2s-prepared-stage-carrier.ts` adds disjoint
module-authentic production and test registries, internal stage/role/job/member
derivation, exact predecessor replay binding, idempotent same-byte preparation,
conflict rejection, and one anti-replenishing production semantic slot.
`s2s-stage-upload-assertion.ts` adds the fixed 1/2/3-attempt ledger topology,
atomic `Ref.modify` reservation, and `Effect.acquireUseRelease` burn semantics.
`s2s-stage-upload-outcome.ts` admits only the seven frozen v16 outcomes and
never authorizes retry or external exactly-once claims. The positive probe and
all generic append/use/seal mechanics are explicitly test-only; production
paths fail with `PRODUCTION_ASSERTION_SHELL_OPEN`. The 33 new focused tests and
343 full package tests close only this process-local mechanics gate.

The reviewed ownership and gate order remain in the immutable
[`v16 stage-upload assertion design handoff`](../../../docs/operations/HSWM_SWM0W_S2S_STAGE_UPLOAD_ASSERTION_DESIGN_NEXT_SESSION_2026-08-23.md)
and
[`v16 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v16.json).
The prior root-private golden vertical composition remains test-only as recorded
by the
[`v15 implementation handoff`](../../../docs/operations/HSWM_SWM0W_S2S_GOLDEN_VERTICAL_COMPOSITION_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and
[`v15 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v15.json).
Local receipts still cannot satisfy production confirmatory events or
`S2SArtifactEvidence` inputs.

Earlier immutable checkpoints remain indexed by the
[`v14 golden design handoff`](../../../docs/operations/HSWM_SWM0W_S2S_GOLDEN_VERTICAL_COMPOSITION_DESIGN_NEXT_SESSION_2026-08-23.md)
and
[`v14 KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v14.json),
the
[`v13 durable replay-profile handoff`](../../../docs/operations/HSWM_SWM0W_S2S_DURABLE_REPLAY_PROFILE_INTEGRATED_NEXT_SESSION_2026-08-23.md)
and
[`v13 KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v13.json),
and the
[`v12 stage-read replay-core handoff`](../../../docs/operations/HSWM_SWM0W_S2S_STAGE_READ_REPLAY_CORE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and
[`v12 KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json).

At code checkpoint `0fe7791`, the root-private selector-free Effect assertion
service and replay snapshot are implemented. One scoped Layer claim owns one
exact `Effect.acquireUseRelease` lease; the shell derives the 1/2/3-attempt
selectors internally, revalidates raw GitHub-shaped observations and strict
stored ZIP/member bytes, builds the structural postcondition, and issues only
module-authenticated opaque completion/replay values. The remaining
archive-receipt `Date.now()` path now uses the Effect Clock. All 364 package
tests pass, including the inherited hostile matrix under the disjoint
`TEST_ONLY_NON_AUTHORIZING` Layer.

The production root remains deliberately fail-closed and has not executed.
There is still no genuine issued production bearer, filled
upload-postcondition profile occurrence, complete-stage durable
commit/recovery, reviewed workflow
authority, GitHub-origin evidence, external shared durability,
independent-process recovery, preregistration, future randomness, dispatch,
event 10, or scientific verdict. This checkpoint changes only `Pi`; `H`, `W`,
`A`, and `F` remain unchanged, and the outcome-bound causal-learning loop did
not advance. First freeze the workflow process-continuity topology; then run
the bounded external shared-POSIX feasibility proof before one complete-stage
program and independent recovery.

The v20 read-only architecture audit freezes a prerequisite for workflow
wiring: process-local object/`WeakMap` bearers do not cross ordinary GitHub
Actions step processes. The reviewed workflow must either retain one trusted
long-lived Effect root or define independently authenticated deterministic
reacquisition; serialized capabilities and trusted evidence remain data, not
authority. The production shell owns the real observer internally, uses one
Effect Clock for sleeps and timeouts, issues completion only after strict
postcondition revalidation, and remains fail-closed until workflow bytes and
process continuity are resolved. Its immutable contract remains in the
[`v20 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v20.json)
and
[`v20 architecture-audit handoff`](../../../docs/operations/HSWM_SWM0W_S2S_ASSERTION_SHELL_ARCHITECTURE_AUDIT_NEXT_SESSION_2026-08-23.md).

The v21 implementation retains that prerequisite exactly. The production
preflight checks workflow source and then the separate process-continuity gate
before config, authority, capability, claim, observer, transport, or I/O.
Neither gate is bypassed by the test Layer, and serialized values never restore
authority. Resume from the v21 handoff above; do not wire a workflow until the
process topology is reviewed and frozen.

The earlier
[`v11 lookup-trace/shared-Layer handoff`](../../../docs/operations/HSWM_SWM0W_S2S_LOOKUP_TRACE_SHARED_LAYER_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and
[`v11 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json)
also remain immutable historical checkpoints.

The in-memory Layer's static capability-ID allowlist is configuration for tests
and local scaffolding, not identity authentication. This slice is not evidence
of learned set-to-set `W`, durable causal learning, or a complete HSWM. A
production store, capability verifier, and outcome/provenance verifier are still
required before durable use.

Run the exact local verification surface with:

```sh
npm ci --ignore-scripts --no-audit --no-fund
npm run verify
```
