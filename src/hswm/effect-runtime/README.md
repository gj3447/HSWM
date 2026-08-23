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
[`current golden vertical-composition implementation handoff`](../../../docs/operations/HSWM_SWM0W_S2S_GOLDEN_VERTICAL_COMPOSITION_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and its
[`v15 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v15.json).
The root-private composition is now implemented with a distinctly typed
test-only golden artifact/postcondition codec, an explicit-root create-only
file Layer, two candidate readbacks, fresh same-root Layer recovery, exact
golden-verifier/numeric-executor runtime-source binding, and an immediate typed
`VOID` terminal. One pinned public-seed run completed with exit zero and
`CANDIDATE_PASS_AWAITING_BUNDLE`, but only as
`TEST_ONLY_NON_AUTHORIZING / NUMERIC_CANDIDATE_ONLY_UNJUDGED`.

The harness remains absent from the package-root export and does not call the
production job sequence, success profiles, or durable evidence store. Local
receipts cannot honestly satisfy the production confirmatory-event and
`S2SArtifactEvidence` carrier inputs, and no projection adapter or relabeling
call site exists. Only 20 of the 48 healthy-success slot occurrences have
construct-and-recover validation, so the implementation does not close a
complete profile. The Effect runtime owns orchestration, authority, resources,
typed failure, and evidence, while the pinned Python/NumPy process remains the
bounded deterministic numeric function cell. The immutable
[`v14 design handoff`](../../../docs/operations/HSWM_SWM0W_S2S_GOLDEN_VERTICAL_COMPOSITION_DESIGN_NEXT_SESSION_2026-08-23.md)
and
[`v14 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v14.json)
record the predecessor contract. The preceding
[`v13 durable replay-profile integration handoff`](../../../docs/operations/HSWM_SWM0W_S2S_DURABLE_REPLAY_PROFILE_INTEGRATED_NEXT_SESSION_2026-08-23.md)
and
[`v13 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v13.json), plus the
[`v12 stage-read replay-core handoff`](../../../docs/operations/HSWM_SWM0W_S2S_STAGE_READ_REPLAY_CORE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and
[`v12 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json)
remain immutable historical checkpoints. The canonical
predecessor-linked envelope and create-only shared-POSIX B/stage claim substrate
are implemented. The replay prerequisites and top-level healthy-success
attachment rosters are also fixed. Successful artifact lookup traces are now
complete in memory, and the bounded stage-read representation, structural
validator/builder, profile caps, and reserved-slot local durable integration are
implemented. The remaining nested attachment semantics, full registration
source snapshot, failure/VOID profiles, closed stage programs,
mandatory-upload postconditions, external storage wiring, and the terminal
finalizer remain OPEN. Production remains dormant while workflow bytes and one
literal API path selection are OPEN. The next claim-critical step is one thin
non-authorizing golden/public-seed dry run that composes the existing numeric
oracle with a distinct test-only golden upload/readback postcondition. Implement
the non-interoperable artifact/postcondition codec first, then runtime identity
binding, the fixed-role test Layer, and the lazy composition. Design the
genuine-authority production carrier connector separately. Run the real
approximately 60-cell workload only as an opt-in Proxmox scratch job. A
generalized hostile matrix is deferred unless that vertical slice exposes a
concrete failure.

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
