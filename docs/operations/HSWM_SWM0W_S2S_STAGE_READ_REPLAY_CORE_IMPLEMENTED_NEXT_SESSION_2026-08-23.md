# HSWM SWM-0W-S2S stage-read replay core implemented handoff

Date: 2026-08-23

Code checkpoint: `955beb04e0ad59b86af8dab7e2a83edde9383196`

V11 continuation predecessor:
[`HSWM_SWM0W_S2S_LOOKUP_TRACE_SHARED_LAYER_IMPLEMENTED_NEXT_SESSION_2026-08-23.md`](HSWM_SWM0W_S2S_LOOKUP_TRACE_SHARED_LAYER_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)

V11 handoff commit: `9853060c4a6c838f8d25aaad24f97c2804adbd89`

V11 code checkpoint: `91b1153bb496737a4c1163b417efc833f74e1418`

Companion representation decision:
[`HSWM_SWM0W_S2S_STAGE_READ_REPLAY_REPRESENTATION_DECISION_2026-08-23.md`](HSWM_SWM0W_S2S_STAGE_READ_REPLAY_REPRESENTATION_DECISION_2026-08-23.md)

Companion local KG projection:
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json)

Authority: the strict TypeScript/Effect direction is `USER_PRIMARY`; the
representation, implementation boundary, audit findings, and continuation order
below are `SECONDARY_AI_PROPOSED` engineering claims.

Status: `BLOCKED_PRE_PREREG /
STAGE_READ_REPLAY_REPRESENTATION_AND_RESOURCE_CONTRACT_FROZEN /
BOUNDED_STRUCTURAL_REPLAY_CORE_ENGINEERING_CLEAR /
AGGREGATE_HOSTILE_AND_EVERY_PHASE_MATRIX_OPEN /
CLOSED_STAGE_PROGRAMS_OPEN / GITHUB_ORIGIN_NOT_OBSERVED /
SCIENTIFIC_UNJUDGED`.

This is the current human-readable continuation entrypoint for code commit
`955beb0`. It supersedes v11 only for continuation; v11 and its v1-through-v11
predecessor chain remain immutable evidence of the earlier state. The companion
v12 file is a local repository KG projection, not HSWM cognition, a remote KG
publication, preregistration, GitHub evidence, or a scientific result.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
Its evolving hypergraph remains one living harness, world model, and continuous
learner. This checkpoint changes a bounded evidence boundary around a future
confirmatory run; it is not a new HSWM subsystem.

- `H`: unchanged. No hypergraph topology, world-state rewrite, memory, or
  cognition result was produced.
- `W`: unchanged. No semantic macro-weight, routing weight, eligibility, or
  causal-credit update was learned.
- `A`: unchanged. No token activation, coalition, or readout efficacy was
  measured.
- `F`: unchanged. No confirmatory function-cell, Python numeric result, drand
  result, candidate, or adjudication was executed.
- `Π`: advanced. The successful predecessor-artifact read can now be encoded as
  one bounded deterministic carrier and reconstructed against current-run,
  predecessor-chain, archive, download, permit, and candidate-pair evidence.

The outcome-bound causal-learning loop did not advance. Tests establish an
engineering boundary; they are not HSWM learning or scientific evidence.

## Frozen runtime direction

The control runtime remains strict TypeScript-first with the installed versions:

- TypeScript `5.9.3`;
- Effect `3.22.1`;
- Node `24.13.0`.

The replay module follows a pure `Either` core plus lazy typed Effect-shell
architecture. More exactly, the core is pure with respect to ambient runtime
services while explicitly snapshotting the bounded callable readers supplied in
its input:

- `buildS2SStageArtifactReadReplay`,
  `validateS2SStageArtifactReadReplay`, and
  `validateS2SCandidateReadReplayPair` are synchronous deterministic domain
  boundaries returning `Either` with `S2SStageArtifactReadReplayError` on the
  expected failure side;
- the corresponding `...Effect` functions use `Effect.suspend`, so construction
  and validation, including supplied getter/reader invocation, do not occur when
  the Effect value is merely created;
- no network request, filesystem write, clock read, randomness, or runtime
  execution occurs inside the replay core;
- the core does synchronously snapshot bounded caller-supplied byte readers.
  Those callable surfaces are therefore part of the residual P1 boundary
  described below, rather than being silently called “pure data”;
- all replay constructors, validators, errors, types, constants, and Effect
  shells remain absent from the package root. Direct internal-module visibility
  is root-private containment, not cryptographic isolation.

The `effect-ts-functional` skill governed the version match, pure-core/lazy-shell
split, typed expected failures, package-root containment, and verification. It is
not a runtime dependency or an HSWM capability.

## What commit `955beb0` implements

### Exact deterministic two-member carrier

One `hswm-swm0w-s2s-stage-artifact-read-replay/v1` carrier is a deterministic
stored ZIP containing exactly, and in order:

1. `manifest.json`: one canonical ASCII JSON line with an aggregate self-hash;
2. `observations.bin`: the exact retained GitHub JSON bodies concatenated in
   ledger order.

The frozen ZIP dialect uses stored entries, fixed ASCII names, signed 16-byte
data descriptors, fixed file metadata, no extra fields or comments, and one
end-of-central-directory record. Its exact framing is:

```text
2 * (30-byte local header + 16-byte descriptor + 46-byte central header)
+ 2 * (len("manifest.json") + len("observations.bin"))
+ 22-byte end record
= 2 * 92 + 2 * (13 + 16) + 22
= 264 bytes
```

The hard budgets are:

| Component | Maximum |
|---|---:|
| `manifest.json` | 1,048,576 B |
| `observations.bin` | 11,534,336 B |
| exact ZIP framing | 264 B |
| complete replay carrier | 12,583,176 B |

For a successful lookup on poll `p in {1,2,3}`, the carrier has exactly
`5 + 2p` observation bodies: `7`, `9`, or `11`. The ordinal-specific raw-body
caps are therefore `7`, `9`, or `11` MiB, with each individual GitHub JSON body
still capped at 1 MiB.

The downloaded predecessor archive is not duplicated as a third member. The
manifest instead content-addresses the exact upload attachment in the recovered
predecessor evidence:

- registration reads reference the `REGISTER` stage attachment
  `upload/registration_archive.zip`;
- candidate reads reference the `CONFIRM` stage attachment
  `upload/candidate_archive.zip`.

The reference includes source stage, source manifest and claim hashes, logical
name, role, schema version, media type, byte length, and raw SHA-256. Validation
requires the actual referenced bytes and rehashes them; a digest string without
available bytes is rejected.

This content-reference design resolves the v11 contradiction between an
admitted 64 MiB candidate archive and the old 16 MiB replay profile without
raising the generic 64 MiB per-attachment or 256 MiB total-attachment substrate
limits. All four replay attachment profiles now use the exact 12,583,176-byte
cap. The resulting success-profile maxima are:

| Stage | Attachments | Attachment maximum total |
|---|---:|---:|
| `REGISTER` | 13 | 108,068,864 B |
| `CONFIRM` | 17 | 112,484,616 B |
| `ADJUDICATE` | 18 | 74,670,872 B |

These are acceptance limits, not resident-heap or economical-execution claims.

### Unknown-input reconstruction and validation

The validator accepts one unknown root and fails closed through typed errors. A
successful result requires all of the following:

1. The root is one exact plain data record containing only `carrierBytes`,
   `currentRunEvidence`, and `predecessorRecovery`. Accessor-backed, proxied,
   symbolic, excess, subclassed, shared-memory, and over-cap carrier surfaces
   are rejected at the applicable boundary.
2. Current-run evidence is reconstructed from an exact schema, its self-hash is
   recomputed, and its stage, current job, predecessor job roster, timestamps,
   workflow lineage, and four seed observations are checked.
3. The carrier is copied, bounded, hashed, and parsed through the exact stored-
   ZIP validator. Member roster, order, framing, canonical manifest bytes,
   manifest schema, and aggregate self-hash are rechecked.
4. Observation descriptors must be ordinal, phase-correct, contiguous,
   non-overlapping, individually bounded, and exhaustive of
   `observations.bin`. The aggregate blob length and hash must match.
5. Every raw slice is reconstructed through the existing validator for its
   kind: workflow run, workflow-attempt jobs, run artifacts, or exact artifact.
   Raw-body hash, projection hash, request ID, ETag, observation time, receipt,
   and expected run/artifact identity must all agree with reconstruction.
6. Poll topology is exact. Earlier polls contain no target artifact, the final
   poll contains exactly one, all run/head/job and chronological bindings hold,
   and readback-start, artifact requery, download, and readback-end follow the
   fixed sequence.
7. The recovered predecessor chain is exactly `[REGISTER]` for `CONFIRM` and
   `[REGISTER, CONFIRM]` for `ADJUDICATE`; `latest` is the same final stage
   object. Every stage success envelope and claim is independently revalidated,
   current-run lineage and predecessor job IDs match, and the `REGISTER ->
   CONFIRM` manifest/claim link is exact where present.
8. The referenced source attachment is unique, descriptor-exact, available,
   length-matching, and hash-matching. The GitHub download receipt is replayed
   over those bytes, and the role-specific archive and member roster is freshly
   validated. Registration requires `control_receipt.json`; candidate requires
   `control_receipt.json` plus `numeric_candidate.json`.
9. Artifact evidence and archive/member projections equal fresh reconstruction.
   Permit evidence is independently decoded and self-hash checked against the
   same current-run evidence. Its identity, operation, full fixed phase topology,
   and exact observation/download ledger mapping must match the replay.
10. Candidate replay fingerprints are recomputed from artifact ID, name, byte
    length, API digest, downloaded-archive digest, and validated-archive digest.
    FIRST/REREAD comparison additionally requires the correct operations, the
    same source/current identity and bytes, the same permit authority, and one
    exact cumulative permit-ledger prefix.

Successful snapshots expose defensive carrier, observation-blob, archive, and
manifest reads. The builder constructs the canonical manifest and two-member
ZIP, then sends its own output through the same unknown-input validator rather
than treating producer output as independent proof.

### Module-issued authenticity boundaries

Two process-local `WeakSet` boundaries close structural-copy minting paths:

- `s2s-live-artifact.ts` records each module-issued
  `S2SValidatedStageArtifactRead`. The replay builder rejects a copied or forged
  object even when it has the same fields and `_tag`.
- `s2s-stage-artifact-read-replay.ts` records snapshots created only after full
  replay validation. Candidate FIRST/REREAD comparison accepts only those
  module-issued replay snapshots.

These sets prevent shallow same-module structural forgery. They do not prove
GitHub origin, survive process restart, coordinate separate module copies,
provide cross-worker or cross-process one-use authority, or replace durable
evidence.

## Re-audited P0 fixes included in `955beb0`

The implementation was re-audited while it was being built. The following
initially exposed P0 gaps were repaired before the checkpoint was accepted:

- the 75 MiB candidate-component versus 16/64 MiB cap contradiction was closed
  by the exact predecessor content-reference representation and derived cap;
- the stored-ZIP builder and validator now pin the exact two-member dialect and
  264-byte framing instead of relying on a coarse archive estimate;
- all four success-profile replay maxima use the one contract constant, with
  exact-cap and maximum-plus-one regressions;
- the builder now requires a module-issued validated read, not merely a
  TypeScript-shaped object;
- predecessor recovery now requires the exact chain length, order, `latest`
  identity, success profile, claim, workflow-file/contract lineage, predecessor
  job IDs, and manifest/claim link;
- a correct archive digest with missing, throwing, corrupt, or wrong-stage
  source bytes fails closed rather than being accepted as availability proof;
- replay validation reconstructs raw observations and rejects a coherently
  rehashed manifest whose compact metadata differs from those bytes;
- candidate pairing now requires independently validated snapshots, the same
  current-run receipt, the same permit authority, and an exact cumulative
  permit-ledger prefix, not fingerprint equality alone;
- pure-to-Effect wrappers are suspended, so hostile recovery access is lazy and
  expected failures remain in the typed error channel;
- replay, permit validator, ZIP builder, validated-read brand check, and all
  related types remain package-root-private.

## Verification at the checkpoint

The following commands were rerun at HEAD
`955beb04e0ad59b86af8dab7e2a83edde9383196`:

- full Effect package suite: `262/262` tests in `21/21` suites;
- focused public/profile/live-artifact/permit/ZIP suite: `55/55` tests in
  `5/5` suites;
- `npm run check`: strict TypeScript pass;
- `npm run build`: pass;
- `npm pack --dry-run`: pass, including the new replay contract and replay
  implementation modules in the package contents;
- `git diff --check`: pass.
- v12 KG contract: `6/6` tests pass;
- complete v1-through-v12 handoff chain: `56/56` tests pass.

The focused suite pins the exact byte formula and profile caps, deterministic
poll-three golden carrier and manifest hashes, unknown-input replay,
coherently-rehashed tamper rejection, unavailable predecessor bytes,
defensive-copy surfaces, module-issued read/replay boundaries, current-run and
permit-prefix candidate pairing, root containment, and stored-ZIP dialect.

These are local deterministic engineering tests. Test scenarios use
`TEST_ONLY_NON_AUTHORIZING` observations and in-memory predecessor recoveries.

## Residual P1 hardening

The structural core fails closed on the hostile cases presently tested, but two
callable trust surfaces remain unbranded:

1. `S2SDurableEvidenceRecovery` itself is not a module-issued snapshot. Its
   `chain` and `latest` properties are read through an unknown boundary and may
   be getter-backed. The Effect shell keeps those reads lazy, but execution can
   still invoke caller code.
2. Recovered envelope attachment `readBytes` functions, and related nested byte
   readers, are callable and unbranded. They are bounded, copied, rehashed, and
   rejected on throw or drift where covered, but the type alone does not prove
   stable durable-store provenance.

A future hardening slice should either issue an authenticated recovery snapshot
from the durable-store module or snapshot these surfaces once behind a narrower
port. It must preserve lazy execution and typed failures; it must not cast the
problem away.

The aggregate hostile matrix is also incomplete. Existing tests do not yet
exhaust every accessor/proxy/cycle/alias shape, every nested receipt
substitution or reorder, repeated/drifting/throwing readers, every actual
carrier/member exact-max and maximum-plus-one boundary, or failure and
interruption at every later stage-program phase with asserted zero retry and
zero downstream I/O. The bounded core is engineering-clear; the wider replay
gate remains open until that matrix and integration surface are complete.

## Exact remaining P0 order

1. Integrate the replay carrier as the exact create-only durable success-profile
   attachment consumed by later closed stage programs, without treating local
   fixtures as production emission or external durability.
2. Complete the aggregate replay hostile and every-phase matrix. Include all
   four operations, poll ordinals, source-chain variants, coherent nested
   rehashes, aliases and readers, actual cap boundaries, and stage-program
   failure/interruption burn semantics. Address the P1 recovery/reader surface
   without weakening laziness or typed errors.
3. Implement the full registration source snapshot: raw B commit, exact A/B
   direct-child and add-only proof, every source-A tracked row and payload,
   pilot-P numeric membership/payloads, and raw A-to-P ancestry witness.
4. Implement and cross-bind the remaining nested replay material: current-run
   snapshot use, registration source replay, Python golden replay, drand
   request/fixture/execution, numeric request and outputs, archive preparation,
   and upload postconditions. Add separate exact success, failure,
   interruption, unknown-publication, upload-failure, and VOID profiles.
5. Implement the six root-private `prepare` / `assert-upload` stage programs.
   Each program must consume the shared current-run/artifact-read Layer exactly
   once, build the required replay attachments, and validate the complete stage
   profile before publication.
6. Wire and independently test one reviewed externally durable shared POSIX
   root across independent processes. Then implement the terminal fresh
   reobservation bracket, rerun invalidation, create-only publication, and
   finalizer.
7. Only after those gates close, author and review the workflow, choose one
   literal workflow API path, and pin its exact bytes and source-A manifest row.
   Source freeze, preregistration, beacon selection, dispatch, and event 10 stay
   later actions rather than engineering-test shortcuts.

## Protected scope and exact nonclaims

The following pre-existing user changes remain uncommitted and protected. They
were not changed by the replay checkpoint or this handoff:

- `src/hswm/experiments/continual_live.py`;
- `tests/test_hswm_continual_live.py`.

Code commit `955beb0` and this handoff do **not** establish any of the following:

- no closed production `prepare` or `assert-upload` stage program exists;
- no workflow source bytes or one reviewed literal workflow API path is pinned;
- no live production Layer successfully issued a genuine current-run or stage-
  artifact capability while the workflow-source policy remains open;
- no GitHub request was made for this checkpoint, and no replay carrier or
  observation has GitHub-origin provenance merely because a fixture passed;
- no production stage emitted, uploaded, downloaded, or read back a replay
  attachment;
- no replay carrier was committed to or recovered from an externally durable
  shared store, and no cross-process availability or one-use property was
  demonstrated;
- the predecessor content reference proves bytes only when the supplied
  recovered chain yields matching bytes; it is not a remote availability
  service;
- no full registration source snapshot, Python/drand nested replay closure,
  cross-attachment stage closure, upload postcondition, or failure/VOID profile
  is complete;
- no exactly-once external effect, same-process cryptographic isolation,
  cross-worker authority, cross-module-copy authority, or cross-process replay
  prevention is claimed;
- no source freeze, preregistration, future beacon, dispatch, candidate,
  adjudication, or event-10 verdict was created;
- no learned `W`, changed `H`, causal-credit assignment, outcome-bound update,
  scientific efficacy result, or HSWM cognition result was produced;
- no remote KG was mutated. The v12 file is only a bounded local repository
  projection and is not HSWM cognition.

This is routine engineering and documentation, not a material research result.
No content-addressed F1 research receipt was created and no
`F1_R8_RESULTS_LOG.md` entry was added.

## Minimal continuation prompt

```text
Continue HSWM from code checkpoint
955beb04e0ad59b86af8dab7e2a83edde9383196. Read
docs/canon/HSWM_CONSTITUTION_2026-08-20.md,
docs/operations/HSWM_SWM0W_S2S_LOOKUP_TRACE_SHARED_LAYER_IMPLEMENTED_NEXT_SESSION_2026-08-23.md,
docs/operations/HSWM_SWM0W_S2S_STAGE_READ_REPLAY_REPRESENTATION_DECISION_2026-08-23.md,
docs/operations/HSWM_SWM0W_S2S_STAGE_READ_REPLAY_CORE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md,
ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json as immutable history,
and ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json as the current
local machine handoff. Apply the effect-ts-functional skill and preserve the
two continual_live user changes.
Stay on TypeScript 5.9.3, Effect 3.22.1, and Node 24.13.0. The exact two-member
content-referenced stage-read replay core is engineering-clear, but production,
GitHub-origin, durable external, hostile/every-phase, nested replay, and science
gates remain open. First integrate the durable replay attachment and finish the
aggregate hostile/every-phase matrix; then implement the full registration
source snapshot and close nested replay/profile semantics before the six
root-private stage programs. Do not create source freeze, preregistration,
beacon, dispatch, candidate, adjudication, or event 10 for engineering progress.
```
