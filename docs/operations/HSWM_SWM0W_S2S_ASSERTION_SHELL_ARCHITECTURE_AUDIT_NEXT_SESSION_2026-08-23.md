# HSWM SWM-0W-S2S assertion-shell architecture audit — next-session handoff

Date: 2026-08-23
Implementation checkpoint: `36b4c9bd45796631e1a9c891eb2f32659da5122a`
Documentation parent: `9ae8cd22833087491e6f368e6a29795f462eb90b`
Continuation KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v20.json`
Predecessor KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v19.json`
Status: `ARCHITECTURE AUDITED / PROCESS CONTINUITY DECISION OPEN / IMPLEMENTATION OPEN / SCIENTIFICALLY UNJUDGED`

## Resume capsule

Resume at the root-private TypeScript/Effect v3 assertion and reconciliation
shell. Do not rework the v19 prepared-carrier, permit, or outcome mechanics
before applying the authority repairs below.

The next code slice advances only the `Pi` control/evidence projection. It does
not change `H`, `W`, `A`, or `F`, and it does not advance the outcome-bound
causal-learning loop. Tests remain evidence instruments rather than HSWM
scientific progress.

Before workflow wiring, resolve one newly explicit integration gate: v16 puts
a pinned `actions/upload-artifact` step between preparation and assertion, but
the current authority and prepared-carrier bearers are object identities held
in module-private `WeakMap`s. Ordinary GitHub Actions steps execute in separate
processes even though their workspace is shared. A serialized capability,
permit, trusted evidence object, or postcondition must never recreate that
authority. GitHub's process boundary is documented in
[workflow syntax for GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax?from=20421).

The workflow therefore remains gate-closed until one of these designs is
reviewed and frozen:

1. one trusted long-lived process/root scope owns preparation, external upload
   coordination, assertion, and completion, with a reviewed replacement for
   the separate pinned upload step or authenticated IPC that keeps the root
   alive and verifies the pinned action result; or
2. a post-action deterministic reacquisition protocol derives a new authentic
   bearer from independently authenticated raw inputs and an independent
   root-of-trust, durable one-slot/create-only CAS, anti-replenishment, and
   restart/worker replay rules, without deserializing authority.

This audit does not select either topology. It records the decision as a
prerequisite, not an implementation result. Determinism alone never establishes
authenticity.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
`docs/canon/HSWM_CONSTITUTION_2026-08-20.md`. Its evolving hypergraph is the
living harness, world model, and continuous learner together. TypeScript,
Effect, GitHub, this repository KG, and MCPs are bounded projections and
interfaces, not separate HSWM cognition, routing, or learning.

Relative to v19, no runtime behavior or scientific evidence changed. This
checkpoint only sharpens the open `Pi` design boundary:

- `H`: unchanged; no topology or living-harness result.
- `W`: unchanged; no learned semantic-weight result.
- `A`: unchanged; no activation or readout result.
- `F`: unchanged; no function-cell or scientific verdict.
- `Pi`: implementation unchanged; production shell ownership, lifecycle,
  timing, completion, and cross-step process continuity are now explicitly
  constrained.
- outcome-bound causal-learning loop: not advanced.

## Frozen production-shell boundary

### Root-private service and Layer

Extend `s2s-stage-upload-assertion.ts`; do not route the current-stage output
through `S2SStageArtifactReads`, which authenticates predecessor reads only.

The root-private Layer constructor accepts only the opaque prepared-carrier
capability and `S2SGitHubLiveTransportConfig`, then captures both internally.
The selector-free `Context.Tag` service operation is zero-argument
(`assertAndRecover`); its caller must not supply a run, stage, role, job,
artifact name, artifact ID, member roster, attempt ordinal, cap, observer,
transport Layer, sleeper, callback, retry policy, or classification.

The root-private live composition must:

1. fail on the existing workflow-source policy or a separate private
   `PRODUCTION_PROCESS_CONTINUITY_POLICY` with status
   `OPEN_UNTIL_TOPOLOGY_FROZEN` before GitHub config, authority inspection,
   prepared-capability inspection, observer/transport construction,
   assertion-scope claim, or I/O;
2. capture the one shared `S2SCurrentRunStage` Layer node;
3. inspect the exact current-run authority and prepared capability;
4. claim one assertion scope through module-private state;
5. only then construct `makeS2SGitHubHttpTransportLiveLayer` and the real
   `S2SGitHubObserverLive` internally, without exposing a transport requirement
   or transport-injection seam; and
6. run the fixed shell under one owning scoped Layer.

Use Effect `3.22.1` only. The lifecycle shape is `Context.Tag` plus
`Layer.scoped`, with `Effect.acquireRelease` for the Layer-owned claim and
`Effect.acquireUseRelease` for the one-use assertion. Expected failures are
typed. Typed failure, defect, interruption, timeout, malformed completion, and
every nonhealthy outcome burn the permit to void. Finalizers remain
infallible. Layer memoization, `Layer.fresh`, or service reconstruction is not
an authority or anti-replay boundary.

Production reserve, append, seal, witness, and finalize operations stay
lexically private and must not reuse the generic `...ForTest` callbacks. A
reservation returns an opaque lease stored in the `Ref`; release compares that
exact lease so a losing concurrent invocation or an unrelated Layer finalizer
cannot close or finalize the winner. `SPENT_SUCCESS` additionally requires a
module-private `WeakSet`-authenticated healthy witness, not a caller-provided
classification-shaped object. Keep one private production root and structured
fibers; do not use `forkDaemon` to escape its scope.

Production must not export an observer- or transport-injected core. A fake
`S2SGitHubObserver` Layer, fake `S2SGitHubHttpTransport`, caller callback, or
caller-selected trusted codec mode would permit evidence laundering. A
separate full-semantics test Layer may exist only behind the disjoint
`TEST_ONLY_NON_AUTHORIZING` registry and may not issue a production completion.

### Exact live topology

The shell owns and revalidates raw observations in this order:

```text
LOOKUP_RUN_START
LOOKUP_JOBS
(LOOKUP_ARTIFACTS_n -> LOOKUP_RUN_END_n -> classify) x 1..3
READBACK_RUN_START
READBACK_ARTIFACT
READBACK_DOWNLOAD_REDIRECT
strict ZIP/member validation
READBACK_RUN_END
seal permit evidence
build and revalidate the structural postcondition
finalize the authentic healthy witness
issue the opaque completion capability
```

Success at attempts 1, 2, and 3 retains the existing exact counts:

| Successful attempt | Observer calls | Stored observations | Permit ledger | Settles |
|---:|---:|---:|---:|---:|
| 1 | 8 | 7 | 12 | 0 |
| 2 | 10 | 9 | 14 | 1 |
| 3 | 12 | 11 | 16 | 2 |

Every observer result is passed through the existing strict
`validateS2SGitHub*Observation` or download validator before classification.
Only a validated absence advances to the next ordinal. Production uses exactly
`Effect.sleep(10_000)` after attempts one and two; it does not use
`Effect.retry`, a caller-injected sleeper, or a caller-injected `Schedule`.

The shell validates current in-progress job semantics, predecessor/later-job
state, run/head/workflow identity, fixed-name uniqueness, non-expiry and
temporal order, exact artifact requery equality, download identity/receipt/
redirect/media type/digest/length, the stored-ZIP dialect, ordered `1/2/2`
member roster, member hashes and byte equality, and the final fresh run
bracket.

### Exact shell outcome mapping

The shell derives outcomes only from validated observations and its own typed
failures:

| Shell condition | Outcome or Effect exit |
|---|---|
| Complete strict readback and postcondition closure | `CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED` |
| Three valid bracketed absences | `BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION` |
| Duplicate, cross-identity, run/head/requery drift, expiry, or impossible time | `DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY` |
| Transport, download, phase timeout, whole-shell timeout, or failed final-run observation | `GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN` |
| Definitive receipt, schema, ZIP, digest, member, or postcondition rejection | `DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE` |
| Defect or interruption | Preserve the Effect `Cause`; void the permit and emit no outcome |

`EXTERNAL_ACTION_FAILURE_OR_UNKNOWN_PROFILE_BRANCH` requires a future
authenticated workflow action branch, and
`COMMITTED_READBACK_FAILED_RECONCILIATION_REQUIRED` requires a future durable
commit/recovery branch. This read-only assertion shell cannot honestly emit
either literal.

All shell-level logical timing uses the Effect Clock so `Effect.sleep`,
`Effect.timeoutFail`, `Clock.currentTimeMillis`, and `TestClock` share one time
source. The HTTP transport keeps a separate native `setTimeout` wall-clock
watchdog for real request safety; it is an inner transport deadline, not the
shell's logical clock. Before the deterministic shell tests close, replace the
remaining direct `Date.now()` in `s2s-live-github.ts` archive-receipt creation
with the Effect clock boundary.

The derived worst-case three-attempt external cap is `1,760,000 ms`: twelve
metadata calls at `120,000 ms`, one archive call at `300,000 ms`, and two
`10,000 ms` settles. Freeze the outer
`WHOLE_ASSERTION_TIMEOUT_MILLISECONDS` at exactly `1,800,000 ms`, leaving a
`40,000 ms` validation/finalization margin. Test the exact aggregate boundary
with `TestClock`; do not reuse the unrelated `480,000 ms` bracket.

### Structural postcondition and authentic completion

Keep `buildS2SStageUploadPostcondition` test-only. Add a separately named,
root-private production-shell assembler whose trusted mode is fixed internally
and which still returns only a non-authorizing structural postcondition. A
caller must never select the mode or pass serialized trusted evidence as
authority.

Build and revalidate the postcondition inside the one-use permit transaction.
The masked successful release program must register the symbol-only opaque
completion in its module-private `WeakMap` and transition the exact lease to
`SPENT_SUCCESS` before returning, with no interruptible gap between those
effects. Registration or witness failure yields void and no completion. A
different Layer finalizer must not close a foreign in-flight lease. The
completion record binds the exact authority object, prepared capability object
and receipt, assertion scope/permit receipt, current-run receipt,
stage/artifact identity, archive hash and length, postcondition receipt/carrier
hash, sole healthy outcome, and defensive raw bytes. Copies, proxies, clones,
serialized evidence, and reconstructed postconditions are data and must fail
the completion inspector.

A separately materialized replay snapshot is also module-authenticated and
revalidates retained bytes. It remains non-authorizing by itself. No result may
claim implicit retry, cross-process replay prevention, historical uniqueness,
durable publication, or external exactly-once behavior.

## Required falsification matrix

- attempts 1/2/3: exact selectors, phases, call/observation/ledger counts, and
  zero/one/two `TestClock` settles;
- three bracketed absences: two exact settles, no readback, reconciliation only;
- duplicate, wrong-run, wrong-head, expired, temporal, requery, download,
  archive, member, and final-run drift at every relevant ordinal;
- all three stages using real action-compatible ZIPs and exact prepared bytes;
- two-caller race with a deferred winner: one winner, loser I/O count zero,
  and loser cleanup unable to close or finalize the winner;
- a separately reconstructed Layer finalizer running while the winner is
  in-flight cannot close that winner's exact lease;
- typed failure, defect, direct interruption, phase timeout, whole timeout,
  and nonhealthy burn with no replenishment on a later call;
- distinct Layer factory objects and separate `Effect.provide` runs using the
  same authentic bearer; Layer memo sharing is not sufficient evidence;
- malformed observer objects and observer objects containing an `outcome`
  property cannot influence classification;
- completion copy/proxy/clone/serialization rejection and defensive byte reads;
- independently exercise workflow-source CLOSED with process-continuity OPEN:
  the production root still causes zero config getter access, authority or
  prepared-capability inspection, scope claim, observer/HTTP transport
  construction, and GitHub I/O;
- package-root absence for assertion service internals, permit leases,
  completion inspectors, and the production structural assembler.

Use Deferred latches before advancing `TestClock`; do not race clock adjustment
against a fiber that has not reached the sleep or timeout. These KG tests
validate the continuation contract only; closing the implementation gate later
requires actual TypeScript Deferred/TestClock/interruption/Layer-recreation
tests, not a passing JSON assertion.

## Next-session execution order

1. Read the constitution, v16 design, v19 handoff/KG, this handoff, the v20 KG,
   and the complete `effect-ts-functional` skill.
2. Preserve the two unrelated dirty continual-live paths listed below.
3. Resolve and document the workflow process-continuity topology before any
   workflow wiring. Never serialize a bearer to bridge ordinary steps.
4. Repair the Effect Clock boundary in `s2s-live-github.ts`.
5. Implement the root-private live assertion service, scoped lifecycle, real
   observer flow, strict ZIP/member validation, production-only structural
   assembler, opaque completion, and replay snapshot.
6. Run the hostile, timing, interruption, concurrency, Layer recreation,
   codec, package-root, and gate-closed matrix above.
7. Keep the production graph fail-closed while workflow source bytes and the
   process-continuity decision remain open.
8. After that gate closes, run the bounded shared-external-POSIX feasibility
   proof, then one complete stage-profile commit and independent recovery.
9. Keep workflow freeze, preregistration, future randomness, dispatch, event
   10, and scientific judgment downstream.

## Exact nonclaims

No production code was added by this audit. No genuine authority, prepared
carrier, assertion scope, completion, replay, live GitHub origin, uploaded
artifact, production profile occurrence, durable root, independent-process
recovery, workflow authority, preregistration, dispatch, event 10, or
scientific verdict was produced. Remote KG publication was not attempted. No
entry belongs in `F1_R8_RESULTS_LOG.md`.

## Protected unrelated worktree paths

These user-owned changes predate this checkpoint and remain untouched:

```text
src/hswm/experiments/continual_live.py
tests/test_hswm_continual_live.py
```
