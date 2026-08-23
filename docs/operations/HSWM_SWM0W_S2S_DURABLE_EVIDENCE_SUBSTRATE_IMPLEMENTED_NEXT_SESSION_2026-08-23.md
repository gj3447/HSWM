# HSWM SWM-0W-S2S TypeScript/Effect durable-evidence substrate handoff

Date: 2026-08-23

Code checkpoint: `893648720007d1c64ffc090a56372a13bb0fd5a8`

Checkpoint parent: `d94a47385470841c5b28a494e125915fecf12803`

Authority: the strict TypeScript/Effect direction is `USER_PRIMARY`; this
implementation boundary and continuation order are `SECONDARY_AI_PROPOSED` and
have been independently adversarially reviewed.

Status: `BLOCKED_PRE_PREREG /
STRUCTURAL_CONTENT_ADDRESSED_ENVELOPE_AND_SHARED_POSIX_CLAIM_ENGINEERING_CLEAR /
COMPLETE_REPLAY_ATTACHMENT_PROFILE_OPEN /
CLOSED_STAGE_PROGRAMS_AND_UPLOAD_POSTCONDITIONS_OPEN /
WORKFLOW_SOURCE_BYTES_OPEN /
GITHUB_ORIGIN_NOT_OBSERVED / SCIENTIFIC_UNJUDGED`.

This is the current continuation entrypoint. It supersedes the
[`v8 stage-artifact permit handoff`](HSWM_SWM0W_S2S_STAGE_ARTIFACT_PERMITS_IMPLEMENTED_NEXT_SESSION_2026-08-22.md)
only for continuation; v8 remains immutable. Its companion
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v9.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v9.json)
is a local repository KG projection, not HSWM cognition, a remote KG
publication, preregistration, GitHub evidence, or a scientific result.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
Its evolving hypergraph remains one living harness, world model, and continuous
learner. The implemented envelope and file store are a bounded evidence
interface around one future confirmatory run; they are not cognition, routing,
or learning subsystems.

Only `Π` advanced (`Pi` in the companion machine projection):

- `H`: target identity unchanged; no topology or cognition result;
- `W`: no learned semantic macro-weight or efficacy result;
- `A`: no activation/readout result;
- `F`: no confirmatory function-cell or numeric result;
- `Π`: canonical content addressing, predecessor-linked structural envelopes,
  and a create-only stage-claim publication/recovery boundary are implemented.

The outcome-bound causal-learning loop did not advance. Event chronology stays
structurally clear only through `1 -> 6 -> 9`; event 10 remains unauthorized.

## Runtime direction

The long-lived control runtime remains strict TypeScript-first with Effect v3:

- TypeScript `5.9.3`, Effect `3.22.1`, Node `24.13.0`;
- canonical identity and envelope validation are deterministic pure kernels;
- expected envelope and filesystem failures use typed error channels;
- commit and recovery are lazy Effects, one Layer owns one semaphore, and each
  filesystem transaction is uninterruptible;
- attachment objects precede the manifest object, and the create-only claim
  anchor is the final publication step;
- Python remains an opaque deterministic numeric oracle.

The `effect-ts-functional` skill governed Effect v3 API selection, typed
errors, laziness, resource/interruption boundaries, Layer ownership, and
hostile tests. The `proxmox-runtime-guardrails` skill governed bounded full
verification and scratch cleanup. Neither skill is a runtime dependency or an
HSWM capability.

## What code checkpoint `8936487` establishes

### Canonical structural envelope and claim

`s2s-evidence-envelope.ts` implements:

```text
hswm-swm0w-s2s-evidence-envelope/v1
hswm-swm0w-s2s-evidence-claim/v1
```

The envelope fixes the experiment, distinct source A and registration B,
attempt one, `head == B`, the current workflow-contract digest, stage and job
identity, workflow source hash, a bounded ordered attachment roster, and the
exact predecessor progression:

```text
REGISTER   -> null
CONFIRM    -> REGISTER manifest + claim hashes
ADJUDICATE -> CONFIRM manifest + claim hashes
```

Each attachment binds logical name, role, optional schema version, media type,
byte length, and raw SHA-256. Logical names and roles are unique; names are
ASCII-sorted in the canonical manifest. The fixed limits are 96 attachments,
64 MiB per attachment, 256 MiB total attachment bytes, 1 MiB manifest bytes,
and 16 KiB claim bytes. Builders and validators reject excess shape,
non-canonical JSON, inconsistent counts or order, missing/extra/duplicate
payloads, hash or length drift, invalid predecessor topology, forged object
shapes, exotic byte views, and shared memory.

Distinct descriptors may intentionally reference the same content hash; this
layer proves byte identity, not stage-specific semantic completeness. It also
carries `workflow_file_sha256` as identity but does not receive or rehash the
workflow source bytes. Both obligations remain with the closed stage programs
and source-freeze boundary.

Manifest and claim documents each carry a canonical-core receipt and also have
a raw-file content address. Snapshots expose defensive copies. The claim binds
the exact envelope identity and manifest address; its create-only filename is
derived from registration B and stage. The private authentic-snapshot WeakSet
avoids redundant large copies in the normal path, but conveys no durable or
cross-process authority.

### Root-private create-only POSIX file store

`s2s-evidence-file.ts` implements the root-private
`S2SDurableEvidenceFileStore` service with lazy `commit` and `recover` Effects.
The caller must supply an already provisioned absolute `0700` root. The Layer
creates and revalidates `objects/` and `claims/`, including device/inode/type
and mode checks, and fsyncs the relevant directories.

Publication order is:

```text
attachment content objects
  -> canonical manifest content object
  -> create-only B/stage claim anchor
  -> full durable-chain recovery and equality check
```

Temporary files use exclusive creation, become `0400`, are fsynced, and meet
the final name through a hard-link compare-and-set. An existing byte-identical
object reconciles; a divergent object at the same digest is
`CONTENT_ADDRESS_CORRUPTION`. An existing byte-identical claim returns
`AlreadyCommitted`; a divergent claim for the same B/stage is
`CLAIM_CONFLICT`. A successor is not written until the exact committed
predecessor is recovered and matched.

Recovery follows every stage from REGISTER through the requested stage,
revalidates the claim, manifest, every content object, exact workflow lineage,
and predecessor hashes, then returns defensive snapshots. Reads use no-follow,
nonblocking flags where supported, verify the opened file identity and size,
and allocate only after bounded stat checks.

Once an exact claim is known to exist durably, a failed post-claim recovery is
reported as `COMMITTED_READBACK_FAILED` with stage, exact claim hash, and typed
cause. A closed stage program must reconcile this state; it must not classify
the publication as absent or automatically VOID merely because the successful
return was not observed.

### Concurrency and interruption boundary

One Layer-owned semaphore serializes local commit/recovery to bound same-process
I/O and memory. Independent Layers and processes sharing the same suitable
filesystem still meet at the hard-link claim CAS. Identical contenders
reconcile to one claim; divergent contenders produce one winner and one
conflict. Content transactions may leave unreferenced objects before a losing
or interrupted claim attempt, but no claim points to incomplete content.

The checked regression races independent Layers inside one process. It does not
simulate separate hosts, process crashes, or power loss; cross-process behavior
is an implementation claim conditional on the stated POSIX filesystem
semantics, not production evidence.

The final claim CAS and full readback are one uninterruptible terminal region.
Process death or external storage failure can still leave a committed claim
without a returned success value, so retry/recovery and
`COMMITTED_READBACK_FAILED` reconciliation remain mandatory.
`PUBLICATION_OUTCOME_UNKNOWN` also remains a typed outcome when exact equality
cannot be established; this slice is not an exactly-once completion claim.

## Exact claim boundary and remaining work

This checkpoint is a structural substrate, not a complete durable replay
closure. `s2s-evidence-envelope.ts` intentionally delegates the exact required
attachment profile to future closed stage programs. Arbitrary structurally
valid attachments do not prove that every input, raw observation, resource
measurement, output, permit receipt, or upload postcondition needed for replay
is present.

The cross-process uniqueness claim also requires every contender for the same
experiment/B/stage to use the same pre-provisioned, externally durable POSIX
root with suitable hard-link and fsync semantics. Different roots do not
coordinate. A runner-local temporary directory is not GitHub artifact storage
or external durability. The caller owns parent-directory durability and must
exclude hostile same-UID writers and path replacement; `0400` is not immutable
against the owning UID. Losing divergent writers may leave orphan content and
this slice has no garbage collector.

The byte maxima are acceptance limits, not an economical memory budget. Full
three-stage recovery can retain all validated stage snapshots and transient
copies. Filesystem calls are individually uninterruptible but have no internal
deadline. These residuals must be accounted for when the production storage
root and stage execution budget are selected.

The envelope currently accepts the two previously reviewed workflow API-path
representations (exact path and exact `@main` path). Production still must
select one literal representation before workflow source freeze.

Still open are the complete stage attachment profiles, closed stage
entrypoints, upload verification postconditions, external storage wiring,
terminal reobservation/finalizer, workflow bytes, one literal workflow API
path, genuine production issuance, GitHub-origin evidence, and the complete
failure/VOID matrix.

## Verification

The code checkpoint passed:

- focused envelope/file-store/root-containment suites: `18/18`;
- full package suite: `234/234` tests in `18/18` suites;
- strict TypeScript check, build, `npm pack --dry-run`, and diff check;
- independent read-only pure-envelope and file-store adversarial audits with no
  blocker inside the declared structural/POSIX scope;
- a follow-up audit of the post-claim error classification with no blocker.
- v9 KG closure regression: `7/7`;
- immutable v1-through-v9 handoff-chain regressions: `36/36`.

The full command ran through bounded Proxmox scratch:

```text
cd src/hswm/effect-runtime
proxmox-scratch run hswm-effect-evidence-envelope-v9 --timeout 7200 -- npm run verify
```

The scratch directory was removed and no long-lived worker remained. These are
engineering results only: tests used local provisioned directories, no external
shared store or production Layer executed, GitHub origin was not established,
and no numeric or scientific verdict exists.

## Exact next-session order

1. Read the constitution, this handoff, the v9 KG, immutable v8, and the
   `effect-ts-functional` skill. Preserve the two protected user changes.
2. Treat `8936487` as the exact implemented code checkpoint. Keep production
   dormant and do not interpret a structurally valid envelope as complete
   replay evidence.
3. Add one root-private, bounded current-run replay-snapshot accessor and freeze
   the REGISTER source/preregistration snapshot contract needed by the closed
   stage programs. Do not expose generic caller-selected storage or evidence
   authority at the package root.
4. Pin the production protocol configuration asset; retain raw drand pulse and
   verification bytes; add Python peak-RSS telemetry; and resolve the existing
   3 MiB versus 4 MiB adjudication-output cap mismatch before declaring a
   complete replay profile.
5. Freeze exact required attachment names, roles, schemas, and bounds for
   REGISTER, CONFIRM, and ADJUDICATE. Then implement the six internal
   `prepare`/`assert-upload` entrypoints and fixed mandatory-upload
   postconditions. A failed or unknown upload must remain typed evidence, not a
   silent success.
6. Wire those programs to one reviewed external shared durable root. Exercise
   identical and divergent independent-process claims and reconcile
   `COMMITTED_READBACK_FAILED`; do not infer cross-job durability from local
   temporary tests.
7. Implement the terminal finalizer only after the stage programs close. Its
   last fresh attempt-one workflow-run, jobs, runs-for-B, and artifact bracket
   must occur immediately before create-only publication, with an explicit
   rerun-invalidation rule.
8. Adversarially enumerate the complete stage/finalizer failure, interruption,
   unknown-publication, and VOID matrix before source freeze.
9. Only then author and independently review the exact three-job workflow. Pin
   its literal raw SHA-256, matching `100644 blob` source-A manifest row,
   resulting workflow-contract digest, and one literal API path.
10. Do not create source freeze, preregistration, a future beacon, dispatch,
    candidate, adjudication, or event 10 merely to advance engineering. Those
    require their own evidence-supported gate decisions.

Routine implementation and documentation do not require a content-addressed
research receipt or an `F1_R8_RESULTS_LOG.md` entry.

## Protected scope and nonclaims

These pre-existing user changes remain uncommitted and protected:

- `src/hswm/experiments/continual_live.py`
- `tests/test_hswm_continual_live.py`

No remote KG was mutated. No closed attachment profile, stage program,
mandatory upload postcondition, external shared store deployment, workflow
source, selected API path, source-A workflow row, GitHub-origin observation,
genuine current-run or stage-read capability, terminal finalizer,
preregistration, beacon, dispatch, candidate, adjudication, event-10 verdict,
learned `W`, or outcome-bound causal update was created.

## Minimal continuation prompt

```text
Continue HSWM from code checkpoint
893648720007d1c64ffc090a56372a13bb0fd5a8. Read
docs/canon/HSWM_CONSTITUTION_2026-08-20.md,
docs/operations/HSWM_SWM0W_S2S_DURABLE_EVIDENCE_SUBSTRATE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md,
ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v9.json, immutable v8, and the
effect-ts-functional skill. Preserve the two continual_live changes. Stay
strict TypeScript/Effect v3 with Python numeric-only. The v1 canonical
structural envelope and create-only shared-POSIX claim substrate are
engineering-clear, but complete replay attachment profiles, closed stage
programs, upload postconditions, external storage wiring, and the finalizer are
OPEN. A local temporary root is not external durability, a structurally valid
envelope is not complete replay evidence, and COMMITTED_READBACK_FAILED requires
reconciliation. Next freeze the exact three-stage attachment profiles and
implement the root-private prepare/assert-upload stage programs after closing
the protocol asset, raw drand, Python RSS, and output-cap prerequisites. Then
implement the fresh terminal reobservation/rerun-invalidation finalizer and full
failure/VOID review. Only afterward author/review workflow YAML and pin its raw
hash, contract digest, source-A manifest row, and one API path. Do not create
preregistration, beacon, dispatch, candidate, adjudication, or event 10 merely
for engineering progress.
```
