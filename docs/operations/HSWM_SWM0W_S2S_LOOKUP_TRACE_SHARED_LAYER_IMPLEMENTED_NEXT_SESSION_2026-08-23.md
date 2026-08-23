# HSWM SWM-0W-S2S lookup-trace and shared-Layer handoff

Date: 2026-08-23

Code checkpoint: `91b1153bb496737a4c1163b417efc833f74e1418`

Primary implementation commit: `84f9eb663759f100193c4b77145fd372de8549b9`

V10 continuation base: `9bd414c5fc063c5ff57afcf745ebaa28c7c13a64`

Authority: the strict TypeScript/Effect direction is `USER_PRIMARY`; the
implemented boundary, audit findings, and continuation order below are
`SECONDARY_AI_PROPOSED` and were independently reviewed.

Status: `BLOCKED_PRE_PREREG /
SUCCESSFUL_LOOKUP_RAW_TRACE_ENGINEERING_CLEAR /
ONE_CURRENT_RUN_LAYER_GRAPH_ENGINEERING_CLEAR /
STAGE_READ_REPLAY_FORMAT_AND_CAPS_OPEN /
WORKFLOW_SOURCE_BYTES_OPEN / GITHUB_ORIGIN_NOT_OBSERVED /
SCIENTIFIC_UNJUDGED`.

This is the current continuation entrypoint. It supersedes the
[`v10 replay-prerequisite handoff`](HSWM_SWM0W_S2S_REPLAY_PREREQUISITES_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
only for continuation; v10 remains immutable. Its companion
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json)
is a local repository KG projection, not HSWM cognition, a remote KG
publication, preregistration, GitHub evidence, or a scientific result.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
Its evolving hypergraph remains one living harness, world model, and continuous
learner. This checkpoint changes only a bounded evidence interface around a
future confirmatory run.

Only `Π` advanced (`Pi` in the companion machine projection):

- `H`: target identity unchanged; no topology or cognition result;
- `W`: no learned semantic macro-weight or efficacy result;
- `A`: no activation/readout result;
- `F`: no confirmatory function-cell or numeric result;
- `Π`: successful artifact lookup now retains its full bounded raw observation
  history, and future current-run replay plus artifact reads can share one
  Effect service instance without changing the legacy read-only Layer output.

The outcome-bound causal-learning loop did not advance. Event chronology stays
structurally clear only through `1 -> 6 -> 9`; event 10 remains unauthorized.

## Runtime direction

The long-lived control runtime remains strict TypeScript-first with Effect v3:

- TypeScript `5.9.3`, Effect `3.22.1`, Node `24.13.0`;
- deterministic trace construction remains a pure frozen-data operation;
- expected runtime failures remain in typed Effect error channels;
- production I/O remains lazy and behind root-private services and Layers;
- callers cannot inject a current-run authority, stage permit, observer, or
  run/head/job/role/artifact selector; they must supply the separately
  authentic registration-B authority plus fixed GitHub transport config;
- Python remains an opaque deterministic numeric oracle.

The `effect-ts-functional` skill governed the Effect v3 Layer graph, functional
core/effect shell, compatibility surface, and verification. The
`proxmox-runtime-guardrails` skill was applied to resource planning; this slice
completed with short bounded local package runs, so no new heavy scratch run or
shared runtime mutation was needed. Neither skill is a runtime dependency or an
HSWM capability.

## What code checkpoint `91b1153` establishes

### Complete successful lookup raw trace in memory

`s2s-live-artifact.ts` now emits
`hswm-swm0w-s2s-artifact-successful-lookup-trace/v1` inside each
`S2SValidatedStageArtifactRead`. The discriminated tuple is exact:

```text
poll 1: [ARTIFACT_OBSERVED]
poll 2: [ARTIFACT_NOT_OBSERVED, ARTIFACT_OBSERVED]
poll 3: [ARTIFACT_NOT_OBSERVED, ARTIFACT_NOT_OBSERVED, ARTIFACT_OBSERVED]
```

The trace also retains the exact initial workflow-run observation and fresh
attempt-one jobs observation used by classification. Every attempt retains the
artifacts observation and following workflow-run observation, including the
zero, one, or two earlier not-observed pairs that the old success path
discarded. The final attempt is the same validated observation pair exposed by
the existing top-level read fields.

The trace object, tuple, and each attempt are frozen. All raw-body accessors
remain defensive copies created by the existing GitHub observation validators.
The trace records the sum of retained raw body lengths and structurally admits
at most eight 1 MiB JSON bodies:

```text
poll 1 lookup maximum:  4 MiB
poll 2 lookup maximum:  6 MiB
poll 3 lookup maximum:  8 MiB = 8,388,608 bytes
```

The successful read still retains three later JSON observations for readback:
readback-start run, exact artifact requery, and final run. Therefore the
derived maximum raw JSON acquisition represented by a third-poll validated
read is 11 MiB (`11,534,336` bytes). That 11 MiB is a derived bound, not yet a
new aggregate replay schema or serializer.

Here, “complete” applies only to the successful lookup phase. Current-run
replay observations, readback observations, download/archive bytes, ZIP
members, and permit evidence remain sibling values or services and are not
inside this trace. Its `schemaVersion` is a discriminant marker, not an Effect
Schema decoder, canonical serialization, aggregate self-hash, or authenticity
proof.

The one-MiB per-observation limit is now pinned by an exact boundary regression:
a valid whitespace-padded JSON body of exactly `1,048,576` bytes is accepted,
and `1,048,577` bytes is rejected. The transport comment now states only a
metadata-observation sub-budget; it no longer claims that complete replay fits
the envelope.

The change adds no retry, no fourth poll, no permit replenishment, and no
production authority. Failure and interruption still expose no partial success
trace and burn the fixed permit according to the pre-existing policy.

### One current-run service for replay and artifact reads

The artifact-read construction is now split into a private Layer requiring
`S2SCurrentRunStage` and two closed production projections:

```text
one current-run Live Layer instance
          |
          +--> retained S2SCurrentRunStage --> snapshotS2SCurrentRunReplay
          |
          +--> sequentially provides --> S2SStageArtifactReads core
```

`makeS2SCurrentRunAndStageArtifactReadsLiveLayer` uses Effect v3
`Layer.provideMerge` to output both services from one current-run Layer node.
This is the root-private composition for a future closed stage program that
needs both replay and fixed reads. The sharing claim is limited to one build,
memo-map, and scope of the returned combined Layer; separate builds or provides
do not share, may attempt separate acquisition, and have no successful-reuse
claim. A prior production permit-scope claim may instead close the process
identity slot.

`makeS2SStageArtifactReadsLiveLayer` remains a two-argument compatibility
projection. Its closed requirement remains `never`, and its output remains
exactly `S2SStageArtifactReads`; it does not newly expose the current-run
service. Both constructors retain the no-observer-override boundary.

While workflow source bytes remain OPEN, both graphs fail with
`WORKFLOW_SOURCE_BYTES_OPEN` before artifact transport configuration or GitHub
fetch. Genuine positive sharing cannot be dynamically demonstrated until the
reviewed workflow source pin opens; after that pin, the required regression is
exactly four current-run acquisition reads, not eight, with the replay receipts
equal to the first four artifact permit-ledger entries.

Only `S2SCurrentRunStage` is shared by this graph. Current-run acquisition and
artifact reads still construct separate GitHub observer/transport Layers. The
combined Layer also does not execute `snapshotS2SCurrentRunReplay` by itself;
the future stage program must consume both services explicitly.

### Package-root containment

The new trace constants/types, combined Layer constructor, validated read
types, read errors, test probe, and all permit mutation functions remain absent
from the package root. The package continues to export only `.`. Direct source
module visibility is a bounded internal projection, not a public capability or
same-process cryptographic isolation boundary.

## Newly explicit P0: replay byte-budget contradiction

No full `hswm-swm0w-s2s-stage-artifact-read-replay/v1` serializer, decoder,
aggregate receipt, or validator exists yet. It must not be implemented against
the current top-level limits without first resolving this contradiction:

```text
maximum validated-read JSON bodies:       11 MiB
registration archive maximum:              4 MiB
registration worst-case raw-component sum: 15 MiB before replay framing

candidate archive maximum:                 64 MiB
candidate worst-case raw-component sum:     75 MiB before replay framing

current read-replay profile maximum:        16 MiB
envelope per-attachment maximum:            64 MiB
```

At the admitted component maxima, a candidate read exceeds its profile by
59 MiB and exceeds even the generic envelope attachment cap by 11 MiB before
any ZIP framing, manifest, aggregate receipt, or base64 expansion. Registration
has only 1 MiB of profile headroom before those additions and is not yet proven
to fit.

The next session must freeze one explicit representation decision before code:

1. raise the read-replay and envelope caps from a derived worst-case budget; or
2. define a content-addressed predecessor/archive reference with durable
   availability and cross-attachment validation instead of embedding duplicate
   archive bytes; or
3. lower the adopted candidate archive/member limits through a separately
   justified protocol change.

Whichever choice is adopted must give exact per-item and stage-total caps,
include framing/manifest overhead, and add exact-max/max-plus-one regressions.
Do not silently truncate, recompress, omit, or trust an archive hash without an
availability proof.

## Verification

The code checkpoint passed:

- full Effect package suite: `245/245` tests in `20/20` suites;
- strict TypeScript check and build;
- `npm pack --dry-run` with the fixed protocol asset included;
- focused trace/Layer/public-containment suite: `56/56` tests;
- exact GitHub metadata-cap suite: `33/33`; combined focused set: `89/89`;
- v11 KG tests: `6/6`; full v1-through-v11 handoff chain: `50/50`;
- `git diff --check`;
- independent read-only trace inventory, Layer-topology audit, and hostile
  replay-boundary audit.

These are engineering tests only. Successful read cases still use
`TEST_ONLY_NON_AUTHORIZING` fixtures. Production remains dormant, so no GitHub
origin, genuine current-run issuance, genuine stage permit, cross-process
one-use property, or scientific outcome was observed. The test probe uses
`Effect.yieldNow()` between polls; it does not prove the production ten-second
settle timing.

## Exact remaining P0 order

1. Freeze the stage-artifact-read replay representation and coherent byte
   budgets described above. Add an ADR or equally explicit typed design record.
2. Implement an unknown-input replay decoder/validator and aggregate self-hash
   only after step 1. It must revalidate every raw observation, ledger mapping,
   download receipt, archive/member byte surface, stage/operation/role/current-
   run binding, poll topology, and candidate-first/reread equality. A shallow
   TypeScript structural value is not authenticity.
3. Add the aggregate hostile suite: excess/missing/accessor/proxy/cycle shapes,
   forged-but-rehashed nested receipts, drifting/throwing readers, byte aliases,
   receipt substitution/reordering, exact caps, and failure/interruption at each
   later phase with zero retry and zero downstream I/O.
4. Build the full registration source snapshot: raw B commit, exact A/B
   direct-child and add-only proof, every source-A tracked row and payload,
   pilot-P numeric membership/payloads, and raw A-to-P ancestry witness.
5. Retain and encode the Python golden replay, drand request/fixture/execution,
   every nested replay, cross-attachment semantics, and separate exact failure,
   interruption, unknown-publication, upload-failure, and VOID profiles.
6. Implement the six root-private `prepare` / `assert-upload` stage programs
   using the combined current-run/artifact-read Layer exactly once per program.
7. Wire and independently test one reviewed externally durable shared POSIX
   root, then implement the terminal fresh bracket and rerun invalidation.
8. Only after those gates close, author and review the exact workflow, select
   one literal workflow API path, and pin its bytes and source-A manifest row.

## Protected scope and nonclaims

These pre-existing user changes remain uncommitted and protected:

- `src/hswm/experiments/continual_live.py`
- `tests/test_hswm_continual_live.py`

No remote KG was mutated. No stage-read replay ZIP, aggregate replay receipt,
full registration source snapshot, nested replay closure, failure/VOID profile,
closed stage program, upload postcondition, external store deployment, workflow
source, chosen API path, GitHub-origin observation, genuine capability,
preregistration, beacon, dispatch, candidate, adjudication, event-10 verdict,
learned `W`, or outcome-bound causal update was created.

Routine code and documentation in this checkpoint are not a material research
result, so no content-addressed research receipt or `F1_R8_RESULTS_LOG.md` entry
was added.

## Minimal continuation prompt

```text
Continue HSWM from code checkpoint
91b1153bb496737a4c1163b417efc833f74e1418. Read
docs/canon/HSWM_CONSTITUTION_2026-08-20.md,
docs/operations/HSWM_SWM0W_S2S_LOOKUP_TRACE_SHARED_LAYER_IMPLEMENTED_NEXT_SESSION_2026-08-23.md,
ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json, and immutable v10.
Apply the effect-ts-functional skill and preserve the two continual_live user
changes. Stay strict TypeScript/Effect v3 with Python numeric-only. The complete
successful lookup raw trace and one-current-run combined Layer are engineering-
clear, but no full stage-read replay exists. First resolve the 75 MiB candidate
read versus 16 MiB profile and 64 MiB envelope-cap contradiction with one
explicit representation/cap decision. Then implement an unknown-input,
self-hashed, cross-bound replay validator and its hostile/cap suite, plus the
full registration source snapshot, before closed stage programs. Do not treat
test-only evidence as production and do not create source freeze,
preregistration, beacon, dispatch, candidate, adjudication, or event 10 merely
for engineering progress.
```
