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
  and independently rereads the candidate. The one-use claim is limited to one
  trusted process/module identity slot; it is not Layer-lifetime or durable
  replay prevention, and the production graph remains dormant while workflow
  bytes are OPEN.
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
[`current next-session handoff`](../../../docs/operations/HSWM_SWM0W_S2S_DURABLE_EVIDENCE_SUBSTRATE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
before composing stage programs, workflow, or a future round. The canonical
predecessor-linked envelope and create-only shared-POSIX B/stage claim substrate
are implemented, but the complete replay attachment profiles, closed stage
programs, mandatory-upload postconditions, external storage wiring, and
terminal finalizer remain OPEN. Production remains dormant while workflow
bytes and one literal API path selection are OPEN.

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
