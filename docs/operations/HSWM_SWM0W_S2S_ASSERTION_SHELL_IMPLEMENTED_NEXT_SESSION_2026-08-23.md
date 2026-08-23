# HSWM SWM-0W-S2S assertion shell implemented — next-session handoff

Date: 2026-08-23
Code parent: `f50d06f4ab86ec74553e774c3846d953e3c3fd28`
Implementation checkpoint: `0fe779164b13d844428d66f977d22d51054d272f`
Documentation parent: `0fe779164b13d844428d66f977d22d51054d272f`
Continuation KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v21.json`
Predecessor KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v20.json`
Status: `ASSERTION SHELL IMPLEMENTED / TEST-ONLY FULL-SEMANTICS FALSIFICATION CLOSED / PRODUCTION ROOT FAIL-CLOSED / PROCESS CONTINUITY OPEN / SCIENTIFICALLY UNJUDGED`

## Resume capsule

The root-private TypeScript/Effect v3 same-stage upload assertion shell is now
implemented and committed. Its full semantics have executed only through a
disjoint `TEST_ONLY_NON_AUTHORIZING` Layer. The production Layer is deliberately
dormant: workflow source bytes are still open and the separately pinned
process-continuity policy is `OPEN_UNTIL_TOPOLOGY_FROZEN`.

The next session must start with the workflow process-continuity topology
decision. Do not add workflow wiring merely because the local shell exists.
After that decision is reviewed and frozen, retain the production gate while
running the bounded shared-POSIX feasibility proof, then attempt one complete
stage-profile commit and independent recovery. Workflow freeze,
preregistration, future randomness, dispatch, event 10, and scientific judgment
remain downstream.

Use the `effect-ts-functional` skill again. The frozen runtime is TypeScript
`5.9.3`, Effect `3.22.1`, Node `24.13.0`, and Vitest `3.2.7`.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
`docs/canon/HSWM_CONSTITUTION_2026-08-20.md`. Its evolving hypergraph is one
living harness, world model, and continuous learner; TypeScript, Effect,
GitHub, the repository KG, and MCPs are bounded projections and interfaces,
not separate HSWM cognition, routing, or learning.

Relative to v20, the conceptual delta is deliberately narrow:

- `H`: unchanged; no topology or living-harness evidence.
- `W`: unchanged; no learned semantic-weight result.
- `A`: unchanged; no activation or readout result.
- `F`: unchanged; no function-cell efficacy or scientific verdict.
- `Pi`: the audited root-private assertion, reconciliation, completion, and
  replay boundary is implemented and test-only falsified.
- outcome-bound causal-learning loop: not advanced.

This is an engineering checkpoint. Tests are evidence instruments for the
`Pi` boundary, not evidence that HSWM learned or that SWM-0W-S2S succeeded.

## Implemented Effect boundary

### Root-private service and lifecycle

`src/hswm/effect-runtime/src/s2s-stage-upload-assertion.ts` now owns a
selector-free `S2SStageUploadAssertion` `Context.Tag`. Its sole operation,
`assertAndRecover`, is zero-argument. Callers cannot inject run, role, stage,
job, artifact, attempt, observer, transport, retry, sleep, timeout, codec mode,
or outcome classification.

The Effect `3.22.1` lifecycle is:

- `Layer.scoped` for the assertion service;
- `Effect.acquireRelease` for one exact Layer claim;
- `Effect.acquireUseRelease` for the one-use assertion lease;
- one Effect Clock for `Clock.currentTimeMillis`, `Effect.sleep`,
  `Effect.timeoutFail`, and deterministic `TestClock` tests;
- typed expected failures, with `Cause.map` translating typed transport or
  validation members while preserving defects, interruption, and composed
  causes;
- infallible release that spends every unsuccessful use as `SPENT_VOID` and
  never replenishes the semantic slot.

The exact owning claim is bound through reservation, runtime, and finalization.
A service escaped from a released Layer cannot consume another Layer's claim.
Closing the owning Layer during an in-flight healthy candidate voids the lease
and cannot leak an unauthenticated completion.

### Production preflight and observer ownership

`makeS2SStageUploadAssertionLiveLayer` evaluates the workflow-source policy and
then the independent process-continuity policy before current-run access,
prepared-capability inspection, Layer claim, GitHub config inspection,
observer/transport construction, or I/O. The live observer Layer surrounds the
entire assertion use, so its resource scope cannot escape.

The production process-continuity policy remains private and open. A direct
test-only preflight probe treats the workflow-source premise as closed and
confirms that the independent process gate still fails. The actual production
root separately proves zero access at the earlier workflow-source gate. This
is source-order and test-probe evidence, not a claim that a production workflow
or GitHub run occurred.

The direct-module test/mechanics exports remain absent from
`src/hswm/effect-runtime/src/index.ts`; package consumers receive no assertion
service, lease, completion/replay inspector, test Layer, or trusted structural
assembler.

### Fixed observation topology

The shell derives all selectors and revalidates every raw observation:

```text
LOOKUP_RUN_START
LOOKUP_JOBS
(LOOKUP_ARTIFACTS_n -> LOOKUP_RUN_END_n) x 1..3
READBACK_RUN_START
READBACK_ARTIFACT
READBACK_DOWNLOAD_REDIRECT
strict stored-ZIP, member-roster, hash, and prepared-byte validation
READBACK_RUN_END
seal exact permit evidence
build and independently revalidate structural postcondition
finalize authentic healthy witness
issue opaque completion
```

Only a validated bracketed absence advances to the next ordinal. Settles are
exactly `10,000 ms`; `Effect.retry` is not used. Successful attempt ordinals
one, two, and three have exact observer call counts `8/10/12`, stored
observation counts `7/9/11`, ledger counts `12/14/16`, and settle counts
`0/1/2`.

The shell validates run/workflow/head identity, the three-job topology,
predecessor success, later-stage non-start, fixed-name uniqueness, expiry at
listing/requery/download time, exact artifact requery, download artifact ID,
endpoint, redirect, media type, length, digest, strict stored-ZIP dialect,
ordered stage member roster, exact prepared member bytes, and the final fresh
run bracket.

### Timing and Clock repair

The remaining archive-receipt `Date.now()` path in
`s2s-live-github.ts` now uses `Clock.currentTimeMillis`. Its deterministic
regression is pinned with `TestClock`. The native HTTP `setTimeout` watchdog is
retained as a real transport safety deadline and is not treated as the shell's
logical clock.

Metadata phases retain `120,000 ms`; download retains `420,000 ms`; the derived
external cap remains `1,760,000 ms`; and the whole assertion use is exactly
`1,800,000 ms`. Boundary tests prove no timeout at one millisecond before the
metadata, download, and whole-use deadlines and failure at the exact deadline.
The finalizer remains outside the interruptible use region as required by
`Effect.acquireUseRelease` and is currently synchronous.

### Structural postcondition, completion, and replay

`buildS2SStageUploadPostcondition` remains fixed to test-only evidence. A
separately named direct-module production-shell assembler fixes trusted mode
internally but still returns only a non-authorizing structural value. Timestamp
expiry is independently checked at successful listing, exact requery, and
download, including cases where GitHub's boolean `expired` field is false.

Production and test completion/replay registries are disjoint module-private
`WeakMap`s. Completion is returned only after the exact witness, Layer claim,
lease, structural postcondition, retained bytes, and registry record all
authenticate after release. Spreads, proxies, `structuredClone`, JSON
serialization, and reconstructed values fail inspection. Retained archive and
carrier byte readers return defensive copies. Replay remains non-authorizing
and process-local; no durable or cross-process anti-replay claim is made.

## Closed test-only falsification matrix

All inherited v20 matrix rows now have executable TypeScript evidence:

| Required row | Result |
|---|---|
| Attempts 1/2/3, exact selectors/counts/settles | PASS — exact `TestClock` boundaries and traces |
| Three bracketed absences, no readback | PASS — two settles, eight calls, permanent void |
| Duplicate/run/head/expiry/time/requery drift | PASS — ordinals 1/2/3 and exact phases |
| Receipt/redirect/media/digest/length/final-run drift | PASS — ordinals 1/2/3 and exact download/final phases |
| REGISTER/CONFIRM/ADJUDICATE Action ZIPs | PASS — exact stage-owned prepared bytes |
| Deferred two-caller race | PASS — one winner and zero loser I/O |
| Foreign Layer finalizer isolation | PASS — exact claim/lease ownership |
| Typed failure/defect/interruption/timeouts | PASS — Cause preserved and lease voided |
| Distinct Layer factories/provide runs | PASS — reconstruction never restores authority |
| Malformed observer/outcome property | PASS — TypeError stays a defect; classification is internal |
| Completion copy/proxy/clone/JSON and defensive bytes | PASS |
| Workflow-source/process-continuity gate ordering | PASS — production zero-access plus independent closed-premise probe |
| Exact `1,800,000 ms` whole-use boundary | PASS |
| Package-root absence | PASS |

This closes only the root-private shell engineering gate with
`TEST_ONLY_NON_AUTHORIZING` execution. Test observations were constructed by
strict validator-backed observers; they are not GitHub-origin observations.

## Verification at the code checkpoint

From `src/hswm/effect-runtime`:

- `npm run check`: PASS;
- Vitest: `29` files, `364/364` tests PASS;
- assertion-shell file: `36/36` tests PASS;
- build: PASS;
- `npm pack --dry-run`: PASS, `223` files, `658.8 kB` package;
- repository `uv run pytest -q`: `2057 passed, 3 skipped`;
- historical v1-v21 handoff contracts: `105/105` PASS;
- `git diff --check`: PASS.

The Effect skill directly shaped the scoped Layer ownership, one-use resource
lifecycle, typed error/Cause discipline, Clock/TestClock boundary, and
functional-core/root-private-effect-shell split. It supplied no scientific
evidence and is not a runtime dependency.

## Production occurrence boundary

Implemented code is not occurrence evidence:

- production same-stage assertion shell: implemented, not executed;
- production completion capability: implemented, never genuinely issued;
- production replay snapshot: implemented, never genuinely materialized;
- production permit-evidence sealing: implemented, never executed;
- current-run, prepared-carrier, and assertion-scope production bearers: not
  genuinely issued;
- GitHub origin/live network run: not established;
- process continuity: unresolved;
- shared external POSIX durability: unproved;
- complete stage-profile commit/recovery: not produced;
- workflow source freeze, preregistration, dispatch, event 10, and scientific
  verdict: not produced.

## Next-session order

1. Read the constitution, v16, v19, v20, this v21 handoff/KG, and the complete
   `effect-ts-functional` skill.
2. Preserve the two unrelated dirty continual-live paths below.
3. Review and freeze one process-continuity topology before any workflow wiring:
   one trusted long-lived Effect root with verified upload coordination, or an
   independently authenticated reacquisition protocol with durable one-slot
   CAS, anti-replenishment, and restart/worker replay rules.
   Never serialize a bearer to restore authority.
4. Keep both production gates closed until the chosen topology and workflow
   source are actually frozen.
5. Run the bounded shared-external-POSIX feasibility proof.
6. Only then implement and exercise one complete create-only stage-profile
   commit and independent recovery with every required attachment.
7. Keep workflow freeze, preregistration, future randomness, dispatch, event
   10, and scientific judgment downstream.

The first next-session action is a reviewed architecture decision, not a code
target. No workflow-wiring implementation is authorized by this handoff.

## Local operational note

Repeated stop-hook messages reported
`/home/lagyeongjun/.orca/agent-hooks/codex-hook.sh: 76: Syntax error: Bad for loop variable`.
At handoff time, `/home/lagyeongjun/.codex/hooks.json` contains an empty
`hooks` object and the current shell script contains no non-POSIX numeric
`for ((...))` loop. No hook file is part of this repository checkpoint.

## Exact nonclaims

No production assertion run, genuine completion/replay occurrence, upload,
GitHub-origin evidence, durable root, historical uniqueness, external
exactly-once behavior, cross-process replay prevention, independent-process
recovery, workflow authority, preregistration, dispatch, event 10, or
scientific verdict was produced. The repository KG and Effect runtime remain
bounded projections and interfaces, not HSWM cognition. No entry belongs in
`F1_R8_RESULTS_LOG.md`; remote KG publication was `NOT_ATTEMPTED`.

## Protected unrelated worktree paths

These user-owned changes predate the implementation checkpoint and were not
staged, committed, or rewritten:

```text
src/hswm/experiments/continual_live.py
tests/test_hswm_continual_live.py
```
