# HSWM SWM-0W-S2S TypeScript/Effect next-session handoff

Date: 2026-08-22

Code checkpoint: `e8706e521e244d1165bb03498123f312ff385e2a`

Checkpoint parent: `46ff65826f9a2a8f91aeee88a133c13344e3326b`

Authority: the TypeScript/Effect direction is `USER_PRIMARY`; the concrete
adapter design and continuation plan are `SECONDARY_AI_PROPOSED`.

Status: `BLOCKED_PRE_PREREG / STRUCTURAL_1_6_9_CLEAR /
ADAPTER_SLICE_ENGINEERING_CLEAR / SCIENTIFIC_UNJUDGED`.

This document supersedes the 2026-08-21 operational handoff for continuation.
It does not rewrite the historical v1 KG projection. The companion
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v2.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v2.json)
is a local repository KG projection, not a remote KG publication, HSWM
cognition, a preregistration, or a research result.

## Read this first

HSWM's target identity remains the one in
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md):
one token-native LLM-function macro-neural network whose evolving hypergraph is
simultaneously living harness, world model, and continuous learner. The present
slice does not divide those roles into separate HSWM subsystems.

The conceptual delta is confined to `Π`, the control and evidence boundary:

- `H`: no new hypergraph cognition or substrate claim;
- `W`: no learned semantic-weight result;
- `A`: no activation/readout efficacy result;
- `F`: the Python numerical oracle is bounded as a function dependency, but no
  valid confirmatory candidate was produced;
- `Π`: strict TypeScript/Effect adapters now acquire, validate, snapshot, and
  retain bounded external observations.

The outcome-bound causal-learning loop has not advanced. Event carriers remain
structurally valid through counts `1 -> 6 -> 9`; no trusted path appends event
10, exposes a verdict, updates learned `W`, or authorizes a future measurement.

## Fixed runtime direction

- The long-lived runtime is TypeScript-first with Effect `3.22.1`, strict
  TypeScript `5.9.3`, and Node `24.13.0`.
- Effect v3 `Schema`, `Context.Tag`, `Layer`, typed `Data.TaggedError`, scoped
  lifecycle, interruption, and immutable snapshots are the runtime idiom. No
  Effect v4 API is mixed in.
- TypeScript owns chronology, source and resource policy, external observation,
  artifact authority, durable control receipts, and eventual evidence-envelope
  composition.
- Python owns deterministic numerical generation, fitting, replay, evaluation,
  and candidate/adjudication receipt bytes. TypeScript hashes those exact bytes;
  it does not parse and reserialize the Python numerical tree.
- Repository ontology and adapters are bounded projections/interfaces. They are
  not HSWM cognition, routing, or learning.

## What code checkpoint `e8706e5` adds

### Policy and event evidence v3

`s2s-confirmatory.ts` now binds exact workflow-run, job, artifact, download,
drand, and Python-execution evidence shapes. The resource-policy SHA is
`5d51316d2aebc8cfa6a7135adba9f167948e096895e3f94caf1defb024a0667d`,
and `s2s-preregistration.ts` pins the same value. There is deliberately no
event-10 composer.

### Strict JSON boundary

`s2s-json.ts` is a bounded UTF-8 JSON parser that rejects duplicate object keys,
non-integer numbers, malformed encodings, excess depth/nodes/bytes, and
non-canonical control values before GitHub projection. This prevents ordinary
`JSON.parse` last-key-wins ambiguity at the authority boundary.

### Read-only GitHub observation and artifact authority

`s2s-live-github.ts` implements exact allowlisted repository Actions endpoints
for run, attempt-one jobs, run artifacts, individual artifact metadata, and ZIP
download. It uses bounded fetches, a rejecting deadline, manual redirects,
cross-origin authorization stripping, response validation, immutable raw-body
and archive getters, strict projections, and self-hashed receipts. Encoded path
traversal, alternate-transport non-200 responses, local/IP redirect targets,
mutable byte aliases, and counterfeit download receipt hashes are rejected.

`s2s-live-artifact.ts` adds a role-aware Layer-scoped authority for the exact
`register`, `confirm`, and `adjudicate` producer jobs. It:

1. observes attempt-one workflow identity;
2. observes the exact producer job and run-wide artifact list;
3. re-observes workflow identity after the list;
4. issues nominal authority only inside that Layer instance;
5. re-observes the run before and after artifact metadata requery, archive
   download, digest/size validation, and exact ZIP validation; and
6. retains the complete run/job/artifact/download observations and immutable
   evidence objects for a future durable envelope.

Three distinct empty artifact-list observations separated by at least ten
seconds yield only `ReconciledAbsentAfterProducerCompleted`, explicitly labeled
`RECONCILED_ABSENCE_NOT_PROOF`. There is no GitHub consistency SLA that turns
three empty lists alone into epistemic proof, and the future workflow has not
yet made a successful upload step a bound producer postcondition.

### Exact-round drand source and verification

`s2s-live-drand-http.ts` can perform one unauthenticated bounded GET only for the
committed Quicknet chain-specific round URL. It has no `latest`, round
selection, retry, redirect-following, fallback, credential, or future-round
path. `s2s-live-drand.ts` snapshots the exact pulse bytes and uses the pinned
bounded offline verifier to check chain, round, previous signature, signature,
randomness, and stable replay projection.

Development exercised historical Quicknet round 1000 only. That smoke check is
not a selected future beacon, confirmatory input, or scientific receipt.

### Fixed Python execution and evidence binding

`s2s-live-python.ts` implements fixed `confirm` and `adjudicate` operations over
the pinned executable/runtime identity and an exact ten-file source closure,
with fixed argv/env/stdin, no shell, no retry, bounded process-group cleanup,
and immutable output bytes. `s2s-python-evidence.ts` binds request, runtime,
source, invocation, and exact output identity without numerical
parse/reserialization.

Only the golden preflight and invalid early-rejection paths were exercised.
No valid candidate or adjudication was run, so this establishes process-boundary
engineering only.

## Exact source anchors

| path | SHA-256 | role |
|---|---|---|
| `src/hswm/effect-runtime/src/s2s-confirmatory.ts` | `7c0211c7edaa63c8460680654541b10fec48aa99197a086496c66c4c34c72cf9` | policy/event evidence v3 |
| `src/hswm/effect-runtime/src/s2s-preregistration.ts` | `99d62417a6a9df146b9617aeaaadf89a2828dbb13e3b6e75928bb33761c67c56` | prereg policy pin |
| `src/hswm/effect-runtime/src/s2s-json.ts` | `a311048ed4fbeb85c1aa7ef5916cce1ce176975e1ac4e2f92da12794f9ae30b9` | strict JSON boundary |
| `src/hswm/effect-runtime/src/s2s-live-github.ts` | `ed52636f7fdb045e8010024c4d74f14ed91bb58e45aef9afcd32189496286e86` | GitHub observer/transport |
| `src/hswm/effect-runtime/src/s2s-live-artifact.ts` | `ac451b914a7250ac49dee892b19b2340e02245521f98d73f86e504bc35370622` | artifact authority/readback |
| `src/hswm/effect-runtime/src/s2s-live-drand.ts` | `54a66da1566e0932aa561739edae9ee9ea1b1dbcb45cf2bcebd7009ca643fea3` | exact-pulse verifier |
| `src/hswm/effect-runtime/src/s2s-live-drand-http.ts` | `dbea3ad3f6ee1975f18089d381108b5946a157381e3f3212325ed3bd0e5e12a1` | exact-round HTTP source |
| `src/hswm/effect-runtime/src/s2s-live-python.ts` | `d9597bbc78426a013481ac3e32d05cf87da61ad79fcf0a185df187e8403744c8` | fixed Python executor |
| `src/hswm/effect-runtime/src/s2s-python-evidence.ts` | `0212baf8dc7f4c160ea889de914ae19b6a2075098031ad495c60a15e0b2a56bf` | Python execution evidence binder |
| `src/hswm/effect-runtime/test/s2s-job-sequence.test.ts` | `5d7522ca056062fc42140669907de6a67b53976e10cfdba948e3b2b1437675af` | v3 structural carrier fixtures |

These hashes are engineering anchors for the committed source. They are not a
content-addressed material-research receipt and do not warrant an
`F1_R8_RESULTS_LOG.md` entry.

## Remaining P0 authority blockers

1. **Request-distinct GitHub provenance is missing.** Observation receipts bind
   endpoint, response bytes/projection, and integer-second local time. Two
   unchanged responses from the same endpoint in one second can therefore have
   the same receipt hash. Capture and validate `X-GitHub-Request-Id`,
   `X-GitHub-Api-Version-Selected`, and an appropriate response validator such
   as `ETag` before treating two calls as durable independent observations.
2. **Artifact authority is still caller-selected.** The bounded service accepts
   `(workflowRunId, expectedHeadSha, role)`. A production root must derive those
   values from a branded validated source/preregistration/dispatch capability;
   it must not expose the raw observer or accept a historical run chosen by a
   caller.
3. **The exact workflow does not exist.** The adapter expects workflow name
   `SWM-0W-S2S confirmatory`, path
   `.github/workflows/swm0w-s2s-confirmatory.yml`, push on `main`, attempt one,
   and jobs `register`, `confirm`, `adjudicate`. No such file is present.
4. **There is no authoritative composition root.** Nothing yet owns the full
   source-A/direct-child-B capability, dispatch identity, exact pulse request,
   Python operations, role-specific artifacts, carrier publication, or VOID
   derivation as one closed Effect program.
5. **There is no durable evidence envelope/store for the new observations.**
   Full immutable receipt objects are returned, but no composition root persists
   them as replayable envelope attachments. Existing carrier journals contain
   event receipt hashes, not this full external evidence closure.
6. **Rerun invalidation must be finalizer-owned.** Adapter bracketing closes
   observed interleavings, but a rerun can begin after any final API check. The
   external finalizer must perform the terminal attempt-one observation
   immediately before create-only verdict publication and define invalidation.
7. **Upload absence is not a VOID fact yet.** The future workflow must bind an
   exact mandatory upload step/output (`if-no-files-found: error`, no ignored
   failure), artifact ID, and producer postcondition. Until then reconciled
   absence remains non-evidentiary.
8. **Event 10 and the full failure matrix remain closed.** No function may
   append `VerifyEvidenceArtifact` or expose `PASS`, `KILL`, or `INCONCLUSIVE`
   until all prior gates are satisfied and independently replayed.

## Hardening after the P0 provenance fix

- Allowlist the pinned GitHub artifact-transfer domains instead of accepting any
  credential-free public HTTPS redirect. Authorization is already stripped;
  this is additional SSRF/confused-deputy reduction.
- Add a GitHub hanging-body timeout regression and a maximum streamed-chunk
  count. The rejecting deadline is implemented, but that body-phase adversarial
  case is not yet locked by a test.
- Add exact JSON node/depth boundary vectors and known-vector observation
  receipt recomputation/tamper tests.
- Decide whether an issued artifact authority is single-use or replayable, and
  apply one aggregate Effect deadline with an injected clock to multi-request
  lookup/readback.
- Export no raw live adapter from the package root until the authoritative
  composition root makes bypass impossible.

## Exact resume order

1. Start at code commit `e8706e521e244d1165bb03498123f312ff385e2a`
   and read this document plus the v2 KG projection.
2. Confirm the two protected user-modified files below remain unstaged and
   untouched.
3. Upgrade GitHub observation/download receipt schemas with request ID,
   selected API version, and retained response validators; add same-second and
   tamper regressions.
4. Define branded, non-forgeable source/preregistration/dispatch authority.
   Derive run ID and head SHA inside the root; do not accept them as public data.
5. Implement stage-specific Effect programs for register, confirm, and
   adjudicate. Each program reconstructs the predecessor carrier, acquires its
   own fresh observations, invokes only its owned Python operation, and persists
   the complete evidence attachments.
6. Add the exact workflow with mandatory uploads and no rerun/matrix ambiguity.
   Audit every pre-spawn, timeout, nonzero, API, upload, readback, and
   publication-unknown path.
7. Implement a separate `workflow_run: completed` finalizer with terminal
   attempt-one recheck, independent adjudication requery/redownload, and
   create-only event-10/operational-reconciliation publication.
8. Re-run full static, unit, integration, workflow, and adversarial review. Only
   then freeze source A, create direct-child add-only B, and select a future
   pulse under preregistration.

The next session must not create the preregistration file, choose a future
beacon, dispatch the confirmatory workflow, or restore any retired canonical KG
write path before steps 3–8 clear.

## Verification at this checkpoint

```sh
cd src/hswm/effect-runtime
npm run verify
```

Result: strict TypeScript, all `143/143` Vitest tests, production build, and npm
pack dry run passed.

```sh
uv run pytest -q \
  tests/test_hswm_swm0w_s2s_worlds.py \
  tests/test_hswm_swm0w_s2s_family.py \
  tests/test_hswm_swm0w_s2s_operator.py \
  tests/test_hswm_swm0w_s2s_training.py \
  tests/test_hswm_swm0w_s2s_protocol.py \
  tests/test_hswm_swm0w_s2s_pilot.py \
  tests/test_hswm_swm0w_s2s_pilot_adoption.py \
  tests/test_hswm_swm0w_s2s_numeric_oracle.py
```

Result: `205/205` passed in 185.89 seconds. Green tests are engineering evidence
instruments, not an S2S efficacy verdict.

## Protected scope and nonclaims

These pre-existing user changes were not staged or modified by this slice:

- `src/hswm/experiments/continual_live.py`
- `tests/test_hswm_continual_live.py`

No future round was selected, no preregistration was created, no confirmatory
workflow was dispatched, no candidate/adjudication result was produced, no
event-10 verdict was composed, no learned `W` was updated, and no remote KG was
mutated. The local v2 KG file exists only so a later coding session can recover
the target/evidence distinction and exact next gate without relying on chat
memory.

## Minimal continuation prompt

```text
Continue HSWM from code checkpoint e8706e521e244d1165bb03498123f312ff385e2a.
Read docs/canon/HSWM_CONSTITUTION_2026-08-20.md,
docs/operations/HSWM_SWM0W_S2S_EFFECT_NEXT_SESSION_2026-08-22.md, and
ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v2.json. Preserve the two
protected continual_live changes. Stay TypeScript/Effect v3, treat Python as
numeric-only, and begin with request-distinct GitHub receipts plus a branded
source/preregistration/dispatch capability. Do not select a future pulse,
create preregistration B, dispatch, or compose event 10 before the gates clear.
```
