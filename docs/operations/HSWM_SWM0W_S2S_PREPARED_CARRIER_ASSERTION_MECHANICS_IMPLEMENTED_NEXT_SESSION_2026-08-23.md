# HSWM SWM-0W-S2S prepared-carrier and assertion mechanics — next-session handoff

Date: 2026-08-23
Code checkpoint: `36b4c9bd45796631e1a9c891eb2f32659da5122a`
Continuation KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v19.json`
Predecessor KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v18.json`
Frozen design: `docs/operations/HSWM_SWM0W_S2S_STAGE_UPLOAD_ASSERTION_DESIGN_NEXT_SESSION_2026-08-23.md`
Status: `PROCESS-LOCAL MECHANICS IMPLEMENTED / PRODUCTION ASSERTION SHELL OPEN / SCIENTIFICALLY UNJUDGED`

## Resume capsule

Resume at the root-private production Effect assertion shell and its replay
snapshot. Do not reimplement the prepared-carrier, one-use permit state
machine, or outcome taxonomy completed at `36b4c9b`.

The new code establishes the module-authentic issuance machinery for a
prepared-current-stage carrier capability, an atomically spent same-stage
assertion permit state machine, and the exact seven-outcome pure classifier.
Its positive execution probe is
explicitly `TEST_ONLY_NON_AUTHORIZING`. Production observation admission,
permit use, and permit-evidence sealing deliberately fail with
`PRODUCTION_ASSERTION_SHELL_OPEN`; no genuine current-run authority, prepared
carrier, or production assertion scope was issued in this checkpoint.

The next slice must co-locate live observation, admission, classification, and
sealing inside one module-local Effect shell. It must not accept a caller
callback as production assertion authority and must not widen the v18 codec's
test-only builder. Serialized `TRUSTED_SINGLE_MODULE_CURRENT_JOB` evidence is
data, never a bearer.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
`docs/canon/HSWM_CONSTITUTION_2026-08-20.md`. Its evolving hypergraph is the
living harness, world model, and continuous learner together. TypeScript,
Effect, GitHub, the repository KG, and MCPs remain bounded projections and
interfaces, not separate HSWM cognition or learning systems.

Relative to v18:

- `H`: unchanged; no topology or living-harness result was produced.
- `W`: unchanged; no semantic-weight learning result was produced.
- `A`: unchanged; no activation or readout result was produced.
- `F`: unchanged; no function-cell or scientific verdict was produced.
- `Pi`: narrowly advanced through module-authentic prepared-carrier machinery,
  atomically one-use assertion mechanics, and a pure non-authorizing outcome
  taxonomy.
- outcome-bound causal-learning loop: not advanced.

The tests below are falsification instruments for this bounded `Pi` contract.
They are not HSWM scientific progress.

## Implemented boundary

### Prepared-current-stage carrier capability

`s2s-prepared-stage-carrier.ts` derives the exact stage policy internally for
`REGISTER`, `CONFIRM`, and `ADJUDICATE`, including role, job, fixed artifact,
archive plan, and the ordered `1/2/2` prepared-member roster. Production and
test capabilities live in disjoint private `WeakMap` registries.

For the production path, the API requires the exact module-issued current-run
authority and authentic predecessor replay snapshots. A single semantic
process slot is anti-replenishing: an identical preparation returns the same
capability object, different bytes fail with `PREPARATION_CONFLICT`, and a
different production bearer cannot claim the slot. Capability fields and
structural copies do not confer authority. Returned bytes are defensively
snapshotted.

The test path is separately named and permanently marked
`TEST_ONLY_NON_AUTHORIZING`; it never reads or writes the production registry.
Because workflow source bytes remain open, no genuine production authority or
prepared capability was issued during verification.

### One-use assertion mechanics

`s2s-stage-upload-assertion.ts` seeds four current-run observations and admits
one exact assertion topology:

```text
current-run bracket
-> lookup run/jobs
-> 1, 2, or 3 fixed-name artifact-list attempts, each closed by run-end
-> readback run/artifact/download/run-end
```

The complete topologies contain `12`, `14`, or `16` ledger entries and produce
`7`, `9`, or `11` postcondition observations. Request IDs and receipt hashes
are unique, times are monotonic, the operation is fixed, and the ledger never
evicts beyond its capacity of `16`.

`Ref.modify` atomically moves the scope from `ISSUED` to `IN_FLIGHT`.
`Effect.acquireUseRelease` then burns it to `SPENT_SUCCESS` only after the
healthy outcome and exact completed topology; typed failure, defect,
interruption, invalid completion, nonhealthy completion, or forged early
healthy completion burns it to `SPENT_VOID`. Closing yields `CLOSED` and never
replenishes the permit.

All generic append, use, evidence-snapshot, and fake-observer probe functions
are explicitly named `...ForTest` and runtime-reject a production scope with
`PRODUCTION_ASSERTION_SHELL_OPEN`. The probe is lazy, returns `void`, owns its
fixed selectors, uses injected settling only for absent attempts, and cannot
return a production bearer or trusted postcondition.

### Pure outcome taxonomy

`s2s-stage-upload-outcome.ts` accepts only these seven exact literals:

```text
CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED
DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE
BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION
DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY
GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN
EXTERNAL_ACTION_FAILURE_OR_UNKNOWN_PROFILE_BRANCH
COMMITTED_READBACK_FAILED_RECONCILIATION_REQUIRED
```

Only the first maps to `Healthy`; the second maps to `DefinitiveFailure`; the
other five map to `ReconciliationRequired`. Every frozen result states
`NON_AUTHORIZING_PURE_CLASSIFIER`, `authorizationClaimed = false`,
`implicitRetryAuthorized = false`, and
`externalExactlyOnceClaimed = false`. Reason/detail/evidence-shaped objects do
not classify.

## Verification

At code checkpoint `36b4c9b`:

```text
npm run check: PASS
focused prepared/outcome/assertion/postcondition tests: 52/52 PASS
new prepared/outcome/assertion tests: 33/33 PASS
Vitest: 29/29 files, 343/343 tests PASS
npm run build: PASS
npm pack --dry-run: PASS, 223 files, 3.6 MB unpacked
v1-v19 handoff/KG chain: 93/93 PASS
git diff --check: PASS
independent Effect v3 authority/concurrency audit: no High or Medium findings
```

The hostile and concurrency matrix covers all stages and successful lookup
ordinals; exact role/job/artifact/member derivation; idempotence and preparation
conflict; defensive bytes; fake, copied, cloned, accessor, and proxy inputs;
test/production registry separation; ledger order, uniqueness, capacity, and
binding; early healthy forgery; permit races; typed failure, defect,
interruption, and nonhealthy burns; and test-local `Context.Tag`/`Layer`
recreation.

No live GitHub run, external upload, remote KG write, or material research
result was produced. No entry belongs in `F1_R8_RESULTS_LOG.md`.

## Exact nonclaims

- The prepared-carrier and permit mechanics are implemented, but no genuine
  production current-run, prepared-carrier, stage-artifact, or assertion
  capability was issued.
- The production live assertion/reconciliation Effect shell is not
  implemented. Production observation admission, permit use, and evidence
  sealing remain fail-closed.
- The test fake observer does not validate real GitHub archive, digest, member,
  request, timing, or download bytes.
- No production `Context.Tag`/`Layer`, bounded real settling schedule, live
  deadline program, or production interruption/recovery program was composed.
- No production upload-postcondition occurrence was filled. The inventory
  remains `48 = 20 + 19 + 9`, with zero production stage-upload occurrences.
- No complete stage profile was durably committed or independently recovered.
- No external shared POSIX feasibility, authenticated durable root,
  independent-process recovery, historical uniqueness, or externally
  exactly-once publication was established.
- Workflow bytes, exact production API-path freeze, sources A/B freeze,
  preregistration, future randomness, dispatch, GitHub origin, event 10, and a
  Q/B/R scientific verdict remain absent.
- No `H`, `W`, `A`, or `F` result changed, and the outcome-bound causal-learning
  loop did not advance.

## Next-session execution order

1. Read the constitution, v16 design, v18 handoff/KG, this handoff, the v19 KG,
   and the complete `effect-ts-functional` skill. Preserve the two unrelated
   dirty continual-live paths below.
2. Implement the root-private production Effect assertion/reconciliation shell
   and replay snapshot. The shell itself must own live GitHub observations,
   exact selectors, observation admission, bounded deadlines/settling,
   classification, and evidence sealing; do not expose a production callback
   seam.
3. Validate actual archive/download/member bytes and build the existing strict
   v18 postcondition only from the module-local completed topology. Keep the
   pure codec builder test-only and return an opaque authentic completion
   capability rather than treating serialized trusted evidence as authority.
4. Keep the production `Context.Tag`/`Layer` graph gate-closed while workflow
   source bytes are open. Exercise real Layer recreation only when the genuine
   authority prerequisites can be met.
5. Run the bounded P0 shared-external-POSIX feasibility proof before broad
   stage/profile expansion: one authenticated namespace/device must support
   create-only hard-link CAS, `fsync`, and parent-directory durability, or the
   storage/runner architecture must change.
6. Then implement one complete create-only stage-profile commit and independent
   recovery path for all three stages, followed by failure/interruption/unknown
   and VOID profiles and the terminal fresh-bracket finalizer.
7. Only after those gates close may the exact workflow be frozen,
   preregistration and future randomness be selected, attempt one be
   dispatched, or event 10 and a scientific verdict be considered.

## Protected unrelated worktree paths

These user-owned changes predated this slice and are not part of code
checkpoint `36b4c9b` or the v19 documentation checkpoint:

```text
src/hswm/experiments/continual_live.py
tests/test_hswm_continual_live.py
```
