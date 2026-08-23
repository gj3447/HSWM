# HSWM SWM-0W-S2S durable replay-profile integration handoff

Date: 2026-08-23

Code checkpoint: `8d9f254c11176a194f74610cfac422dfa67aae08`

V12 continuation predecessor:
[`HSWM_SWM0W_S2S_STAGE_READ_REPLAY_CORE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md`](HSWM_SWM0W_S2S_STAGE_READ_REPLAY_CORE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)

V12 handoff commit: `e8c9cd527be3b72b91c9acc093aeffcab41caa31`

V12 code checkpoint: `955beb04e0ad59b86af8dab7e2a83edde9383196`

Companion local KG projection:
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v13.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v13.json)

Authority: the strict TypeScript/Effect direction is `USER_PRIMARY`. The
critical-path interpretation, bridge boundary, audits, and continuation order
below are `SECONDARY_AI_PROPOSED` engineering claims.

Status: `BLOCKED_PRE_PREREG /
LOCAL_CREATE_ONLY_REPLAY_PROFILE_VERTICAL_SLICE_ENGINEERING_CLEAR /
GOLDEN_STAGE_COMPOSITION_OPEN / WORKFLOW_AND_GITHUB_ORIGIN_OPEN /
SCIENTIFIC_UNJUDGED`.

This is the continuation entrypoint after code commit `8d9f254`. It supersedes
v12 only for continuation. The v1-through-v12 KG files and handoffs remain
immutable historical projections. The v13 companion is a local repository KG
projection; it is not HSWM cognition, a remote KG publication, a
preregistration, GitHub evidence, or a scientific result.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
Its evolving hypergraph remains one living harness, world model, and continuous
learner. The Effect runtime is a bounded control/evidence projection around
that entity, not a separate cognition, router, learner, or world model.

- `H`: unchanged. No hypergraph topology, memory, or world-state update was
  produced.
- `W`: unchanged. No role-aware semantic weight or causal credit was learned.
- `A`: unchanged. No activation, coalition, or readout efficacy was measured.
- `F`: unchanged. No confirmatory function-cell or numeric result was executed.
- `Π`: advanced narrowly. Fully validated predecessor-read replay carriers can
  now occupy their fixed success-profile slots and survive one local
  create-only commit/recovery chain without losing their exact bytes or
  bindings.

The outcome-bound causal-learning loop did not advance. The test suite is an
engineering falsification instrument, not evidence that HSWM learned or that
the SWM-0W-S2S scientific gate passed.

## TypeScript/Effect direction

The production control runtime remains strict TypeScript-first and functional:

- TypeScript `5.9.3`;
- Effect `3.22.1`;
- Node `24.13.0`;
- Vitest `3.2.7`.

The new bridge is one lazy `Effect.suspend` program with typed expected
failures and a required `S2SDurableEvidenceFileStore` service. Deterministic
reconstruction remains in synchronous `Either` cores. Privileged constructors,
validators, store capabilities, and bridge types remain absent from the package
root.

The existing Python/NumPy SWM numeric oracle remains the research oracle; it is
not silently rewritten in TypeScript. TypeScript/Effect owns orchestration,
authority, resources, typed failure, evidence composition, and durable control.
That is the current functional architecture boundary.

The `effect-ts-functional` skill governed the pinned Effect-v3 API choice,
functional-core/effect-shell split, lazy execution, typed errors, Layer service
boundary, root-private containment, and verification. It is an authoring
workflow, not a runtime dependency or HSWM capability.

## What code checkpoint `8d9f254` implements

### Authentic local recovery and one-read source snapshot

`s2s-evidence-file.ts` now marks each file-store-issued recovery with a
process-local `WeakSet`. The recovery chain is an inert frozen data property,
not a caller-controlled getter. The replay core rejects a copied, proxied, or
otherwise unissued recovery before reading any recovery property.

The replay builder and validator select the recovered source attachment once,
copy its bounded bytes once, and reuse that prepared snapshot during producer
self-validation. A counterfeit recovery or attachment getter is rejected
without invocation. This closes the v12 callable-recovery P1 within one loaded
module; it is not cross-process authentication.

### Fixed durable replay-profile bridge

`s2s-stage-read-replay-durable-profile.ts` adds one root-private entrypoint:

```text
commitS2SStageReadReplayProfileAttachments(input)
  : Effect<publication, typed failure, S2SDurableEvidenceFileStore>
```

It accepts no caller-defined slot mapping. The mapping is fixed:

| Consumer stage | Profile slot | Required replay operation | Role |
|---|---|---|---|
| `CONFIRM` | `input/registration_read.zip` | `CONFIRM_READ_REGISTRATION` | `REGISTRATION` |
| `ADJUDICATE` | `input/candidate_first_read.zip` | `ADJUDICATE_READ_CANDIDATE_FIRST` | `CANDIDATE` |
| `ADJUDICATE` | `input/candidate_reread.zip` | `ADJUDICATE_REREAD_CANDIDATE` | `CANDIDATE` |
| `ADJUDICATE` | `input/registration_read.zip` | `ADJUDICATE_READ_REGISTRATION` | `REGISTRATION` |

`REGISTER` is rejected because it has no predecessor-read replay slot.

Before commit, the bridge:

1. rejects proxied, accessor-backed, subclassed, or excess bridge roots without
   invoking hostile getters;
2. strictly reconstructs current-run evidence and the success-profile envelope;
3. exact-compares stage, A/B, run ID and attempt, head, creation time, API path,
   workflow hashes, current job, and predecessor stage;
4. recovers the predecessor from the required store and requires module-issued
   recovery provenance;
5. exact-compares the envelope predecessor stage, manifest hash, and claim hash
   with the recovered latest stage;
6. fully validates each reserved replay carrier against that same current run
   and predecessor chain, then validates the candidate FIRST/REREAD pair;
7. snapshots the validated carrier bytes, descriptors, and replay hashes.

The bridge calls `store.commit` at one source location and never retries a store
failure or unknown publication outcome. After commit, it requires another
module-issued recovery and exact-compares:

- the complete predecessor manifest/claim byte prefix;
- the latest submitted manifest and derived claim bytes;
- the recovered success profile;
- every reserved replay descriptor, raw hash, and carrier byte snapshot.

This postcondition is extensional preservation of carriers that already passed
full semantic replay validation. It deliberately does not claim a second
independent semantic validation after commit.

### Test-only three-stage vertical chain

The integration regression uses the actual local file-store Layer and existing
`TEST_ONLY_NON_AUTHORIZING` artifact observer fixtures:

1. commit `REGISTER` with a validated registration archive;
2. build and prevalidate the `CONFIRM` registration-read carrier;
3. reject a wrong predecessor hash, then commit the exact `CONFIRM` profile;
4. build the `ADJUDICATE` registration, candidate-FIRST, and candidate-REREAD
   carriers;
5. reject swapped candidate operations, then commit the exact `ADJUDICATE`
   profile;
6. receive `AlreadyCommitted` for the byte-equal duplicate, then recover the
   exact three-stage chain from a fresh Layer over the same local root;
7. reject an accessor-backed root without invoking its getter.

The non-replay success-profile slots in this fixture contain minimal
profile-valid placeholder bytes. Their nested semantics are not validated.
Accordingly, this is a durable reserved-slot integration test, not a complete
stage program or production evidence chain.

## Verification and independent audit

At code checkpoint `8d9f254`:

- strict TypeScript check: PASS;
- full Effect package: `263/263` tests in `21/21` suites;
- focused live-artifact/evidence-store/public-containment set: `34/34` tests in
  `3/3` suites;
- build: PASS;
- package dry run: PASS, including the new internal module;
- `git diff --check`: PASS;
- independent read-only P0 audit: GO, no commit-blocking issue.

Two non-blocking defensive regressions remain available if a future vertical
slice needs them: instrument a deliberately wrapped store to count one recover
and one commit/no retry, and reject an impossible publication tag from a
contract-violating store double. Neither is evidence of a real-store failure.

## Target identity versus current evidence

The Occam audit found that the repository already contains the narrow
role-aware set-to-set numeric machinery needed for the SWM-0W-S2S question:
the `T16`, parameter-matched `P_CAP18`, and `DS870` arms; deterministic
training/replay; Q removal/restoration; broadcast and role-cycle controls; and
candidate/adjudication projections. SWM-0R remains representation-conformance
evidence, while the earlier scalar precursor has only narrow support.

None of those facts is a new scientific result in this checkpoint. No future
seed was selected, no confirmatory test split was observed, no preregistration
was created, and no candidate or adjudication ran. Scientific status remains
`UNJUDGED`.

## Explicitly open boundaries

- complete registration source snapshot and its nested semantics;
- Python request/output and numeric candidate/adjudication cross-attachment
  validators inside complete stage profiles;
- drand, invocation, upload, terminal-reobservation, failure, interruption,
  unknown-publication, failed-upload, and VOID profile composition;
- six closed root-private prepare/assert-upload stage programs;
- mandatory artifact upload/readback postconditions;
- reviewed external shared durable-root deployment and authentication;
- exact workflow source bytes, source-A row, and one literal API path;
- genuine GitHub-origin current-run and stage capability issuance;
- rerun invalidation and event-10 finalization;
- source freeze, preregistration, future beacon, dispatch, candidate,
  adjudication, and scientific verdict.

The broad hostile/every-phase matrix is also incomplete. It is no longer ahead
of the claim-critical vertical slice by default; extend it only when the next
slice exposes a concrete aliasing, ordering, resource, or burn-semantics risk.

## Next-session critical path

1. Read the constitution, this handoff, the v13 KG, and the
   `effect-ts-functional` skill. Treat `8d9f254` as the code checkpoint. Preserve
   the unrelated dirty continual-live files listed below.
2. Compose one root-private, non-authorizing golden/public-seed dry run through
   the existing Python numeric oracle and the local three-stage envelope chain.
   Reuse the fixed replay slots and actual create-only store; do not invent a
   second orchestration model.
3. Implement only the nested attachment validators and mandatory
   upload/readback postconditions required by that one path. Every produced
   profile byte must be reconstructed after recovery before the dry run is
   accepted.
4. Use the dry run as the falsifier for the remaining composition design. Add a
   hostile or every-phase regression only for an observed or concrete failure
   mode; do not expand the generalized matrix speculatively.
5. Once the local vertical path is closed, author-review and pin the exact
   workflow bytes, source-A row, and literal API path. Only after that boundary
   is reviewed may a later session create the source freeze, preregistration,
   and future-seed selection in their canonical order.

Do not select a beacon, create a preregistration, dispatch a confirmatory run,
produce a candidate, adjudicate, or compose event 10 merely to mark engineering
progress.

## Protected unrelated work

Do not edit, stage, or restore these pre-existing user changes:

- `src/hswm/experiments/continual_live.py`;
- `tests/test_hswm_continual_live.py`.

## Resume checks

```sh
git status --short
git log -3 --oneline
cd src/hswm/effect-runtime
npm run verify
cd ../../..
uv run pytest -q tests/test_hswm_swm0w_s2s_effect_handoff*.py
```

The first implementation action next session should be the thin local
golden/public-seed numeric-oracle-to-upload/readback composition. Do not resume
from the retired generalized hardening order in v12.
