# HSWM SWM-0W-S2S stage-upload assertion design — next-session handoff

Date: 2026-08-23
Continuation KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v16.json`
Parent checkpoint: `43f2198a1b89634e7f23726fbc6cbb6996da8e53`
Status: `DESIGN FROZEN / IMPLEMENTATION OPEN / SCIENTIFICALLY UNJUDGED`

## Resume capsule

V15 completed only the root-private, local, test-only golden numeric vertical.
This checkpoint audits the first honest bridge back toward the production
SWM-0W-S2S path and freezes its boundary before code is added.

The next gate is not a generic production uploader. The reviewed workflow will
own the pinned `actions/upload-artifact` side effect. Strict TypeScript/Effect
owns two root-private programs around that action:

```text
prepare carrier -> external pinned upload step -> assert/reconcile same-stage artifact
```

The assertion must ignore uploader-returned identity as proof. It derives the
stage, role, job, fixed artifact name, member roster, and caps from authentic
current-stage authority; independently lists the run artifacts; re-queries the
selected artifact; downloads the ZIP; validates exact archive and member
semantics; and emits a replayable upload-postcondition carrier. Unit fixtures
can falsify this behavior, but they cannot establish GitHub origin or fill a
production profile occurrence.

## Canonical role and conceptual delta

HSWM remains the single token-native LLM-function macro-neural network defined
by `docs/canon/HSWM_CONSTITUTION_2026-08-20.md`. Its evolving hypergraph is the
living harness, world model, and continuous learner at once. The TypeScript
runtime, GitHub workflow, evidence store, repository KG, and MCP surfaces are
bounded projections and interfaces; none is HSWM cognition by itself.

Relative to v15:

- `H`: unchanged; no evolving topology or living-harness evidence is added.
- `W`: unchanged; no learned semantic-weight result is added.
- `A`: unchanged; no activation/readout efficacy result is added.
- `F`: unchanged; no confirmatory function-cell verdict is added.
- `Pi`: documentation-only advance: the authority, transaction, observation,
  replay, cap, and recovery boundary for one stage-local upload assertion is
  frozen.
- outcome-bound causal-learning loop: not advanced.

Tests for the later implementation are evidence instruments for this narrow
Pi contract, not HSWM progress by themselves.

## Current evidence and exact gap

The repository already has:

- pure registration, candidate, and adjudication carrier builders in
  `s2s-job-sequence.ts`;
- module-authentic current-run authority and replay snapshots, deliberately
  gate-closed while workflow source bytes are absent;
- fixed predecessor-read permits and independent GitHub readback;
- strict `actions/upload-artifact@v4.6.2` stored-entry ZIP validation;
- replay carriers containing raw GitHub observations;
- create-only durable evidence envelopes and same-process recovery; and
- three 16 MiB success-profile slots named with schema
  `hswm-swm0w-s2s-stage-upload-postcondition/v1`.

The repository does not yet have:

- a module-authentic prepared-current-stage carrier capability;
- a same-stage produced-artifact assertion operation;
- a production stage-upload postcondition codec;
- a complete one-commit stage-profile bridge containing both predecessor
  replays and current-stage upload evidence;
- a reviewed external shared durable root reachable from the fixed jobs;
- workflow bytes, preregistration, genuine run authority, or GitHub-origin
  evidence.

Lifecycle events are currently constructed only in tests, and the three pure
carrier builders have no production call site. `S2SArtifactEvidence` is
honestly constructed only after GitHub API re-query, archive download, and ZIP
validation. A local golden receipt cannot be adapted into any of these inputs.

## Frozen two-phase boundary

### Phase 1: prepare

The root-private prepare program must:

1. start from an authentic `S2SCurrentRunStageAuthority`;
2. derive the fixed stage artifact specification internally;
3. accept only the exact stage lifecycle tuple and predecessor replay inputs;
4. use the existing pure carrier builder;
5. snapshot the exact ordered member names, lengths, hashes, and bytes;
6. issue one module-authentic prepared-carrier capability bound to the current
   run, stage, current job, and member snapshot; and
7. materialize only the fixed upload directory/files required by the future
   workflow entrypoint.

Preparation does not claim publication. The GitHub archive is produced by the
pinned action, so its byte-level identity is not known until independent
download. The prepared capability binds the expected member bytes, not a
fabricated artifact ID or archive digest.

### External action

The workflow, once authored and reviewed, must contain exactly one fixed-name
`actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02`
step between prepare and assertion, with:

- `if-no-files-found: error`;
- `compression-level: 0`;
- `retention-days: 90`;
- `overwrite: false`; and
- `include-hidden-files: false`.

Action outputs may be retained as untrusted diagnostics or compared after
independent selection, but they are never the source of artifact identity,
digest, or success evidence. Internal action retries and distributed service
behavior prevent any exactly-once publication claim.

### Phase 2: assert/reconcile

The root-private assertion program must:

1. consume the same authentic current-stage authority and prepared capability;
2. atomically spend one process-local assertion permit for that bearer;
3. derive every selector and policy internally, with no caller-selected role,
   name, job, path, member roster, or cap;
4. independently observe run and jobs;
5. make at most three fixed-name artifact-list attempts, bracketing each with
   a fresh run observation and bounded settling between absence attempts;
6. reject missing, duplicate, expired, cross-run, cross-head, temporally
   impossible, or ambiguous artifacts;
7. re-observe the run, re-query the selected artifact by independently found
   ID, download it, and re-observe the run again;
8. validate download receipt, API digest, archive size, exact ZIP dialect,
   exact member roster, member hashes, and member bytes against preparation;
9. construct `S2SArtifactEvidence` only from that validated readback;
10. construct the upload-postcondition ZIP from the full observation closure;
    and
11. hand the archive and postcondition to the single complete-stage profile
    commit path for independent recovery and revalidation.

The current producer job is expected to remain `in_progress` with null
conclusion. All fixed predecessors must be completed successfully and no later
fixed job may have started. GitHub's artifact projection lacks a producer job
ID, so the defensible claim is limited to one fixed-name artifact in the
current run/head whose creation time is compatible with the current job. It is
not proof of historical uniqueness or of which internal action attempt created
the artifact.

## Shared stage-artifact specification

One root-private `S2S_STAGE_ARTIFACT_SPECS` value must become the single source
for live readback, replay, upload assertion, and profile validation.

| Stage | Role | Job | Artifact | Archive/profile logical name | Postcondition logical name | Carrier schema | Members | Archive cap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REGISTER | REGISTRATION | register | s2s-registration | upload/registration_archive.zip | upload/registration_postcondition.zip | hswm-swm0w-s2s-registration-carrier/v1 | control_receipt.json <= 1 MiB | 4 MiB |
| CONFIRM | CANDIDATE | confirm | s2s-candidate | upload/candidate_archive.zip | upload/candidate_postcondition.zip | hswm-swm0w-s2s-candidate-carrier/v1 | control_receipt.json <= 1 MiB; numeric_candidate.json <= 60 MiB | 64 MiB |
| ADJUDICATE | ADJUDICATION | adjudicate | s2s-adjudication | upload/adjudication_archive.zip | upload/adjudication_postcondition.zip | hswm-swm0w-s2s-adjudication-carrier/v1 | control_receipt.json <= 1 MiB; numeric_adjudication.json <= 3 MiB | 4 MiB |

The map is not exported from the package root. Existing duplicate policy
fragments must be replaced incrementally only when behavior-preserving tests
show exact equivalence.

## Frozen upload-postcondition representation

Schema version:

```text
hswm-swm0w-s2s-stage-upload-postcondition/v1
```

Representation:

```text
STORED_ZIP_COMPACT_MANIFEST_CONTIGUOUS_OBSERVATIONS_CURRENT_STAGE_ARCHIVE_REFERENCE
```

The deterministic stored ZIP contains exactly:

```text
manifest.json
observations.bin
```

Caps are derived, not aspirational:

- `manifest.json`: at most 1,048,576 bytes;
- each raw GitHub JSON body: at most 1,048,576 bytes;
- successful lookup attempt ordinal: 1, 2, or 3;
- observation count: 7, 9, or 11;
- observation blob: at most 11,534,336 bytes;
- fixed two-member ZIP framing: 264 bytes;
- exact maximum postcondition carrier: 12,583,176 bytes;
- success-profile occurrence cap: 16,777,216 bytes.

The observation tuple is exact:

```text
LOOKUP_RUN_START
LOOKUP_JOBS
(LOOKUP_ARTIFACTS_n, LOOKUP_RUN_END_n) x successful ordinal
READBACK_RUN_START
READBACK_ARTIFACT
READBACK_RUN_END
```

Every compact descriptor binds ordinal, phase, observation kind, contiguous
offset, byte length, raw-body SHA-256, observation time, request ID, ETag,
projection SHA-256, and receipt SHA-256. Reconstruction must reparse every raw
body and recompute the trusted observation and receipt before semantic checks.

The exact manifest key family is frozen as:

```text
schema_version
representation
experiment_id
classification
authority_scope
publication_claim
publisher_return_used_as_evidence
historical_uniqueness_claimed
external_exactly_once_claimed
cross_worker_replay_prevention_claimed
cross_module_copy_replay_prevention_claimed
cross_process_replay_prevention_claimed
durable_replay_prevention_claimed
source_commit_a
current_run_evidence_receipt_sha256
identity
assertion_permit_evidence
stage
role
producer_job_id
producer_job_name
artifact_name
artifact_id
artifact_byte_length
artifact_sha256
successful_attempt_ordinal
observation_count
observation_blob_byte_length
observation_blob_sha256
observations
download_receipt
artifact_evidence
archive_reference
archive_validation
prepared_members
archive_members_equal_prepared_members
postcondition_receipt_sha256
```

Fixed claims are:

```text
classification = PRODUCTION_INTENDED_STAGE_UPLOAD_POSTCONDITION
authority_scope = PROCESS_LOCAL_STAGE_ENTRY
publication_claim = CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED
publisher_return_used_as_evidence = false
historical_uniqueness_claimed = false
external_exactly_once_claimed = false
all cross-worker/module/process/durable replay-prevention claims = false
archive_members_equal_prepared_members = true
```

`archive_reference` binds the same envelope's current-stage archive logical
name, role, carrier schema, media type, byte length, and raw SHA-256. It does
not contain the envelope manifest or claim hash, which would be circular.
`archive_validation` retains archive/expanded/largest-member lengths and the
exact ordered member name, byte length, CRC-32, and raw SHA-256 projection.
`prepared_members` independently records the capability-bound expected member
name, length, and SHA-256 tuple.

The postcondition ZIP is a separate durable attachment. It is never embedded
inside the uploaded artifact that it describes.

## Authority and Effect model

Use Effect 3.22.1 APIs only:

- pure unknown-input decoders, builders, and validators return `Either`;
- GitHub observation and assertion sequencing use lazy `Effect` values;
- root-private services use `Context.Tag` and fixed `Layer` composition;
- one local permit is serialized atomically with `Ref` or the existing permit
  discipline and is never replenished by recreating a service around the same
  bearer;
- expected failures remain tagged in the error channel;
- defects are not converted into evidence or retry permission;
- interruption closes the local assertion scope and never authorizes an
  implicit retry.

The existing predecessor-read permit is not an upload/assertion capability.
The new permit operation is fixed to
`ASSERT_AND_RECOVER_CURRENT_STAGE_ARTIFACT`. Its serializable evidence must say
that the protection is process-local and must make no external exactly-once or
cross-process replay-prevention claim.

The production Layer stays gate-closed while workflow source policy is
`OPEN_UNTIL_WORKFLOW_BYTES_EXIST`. A separately named
`TEST_ONLY_NON_AUTHORIZING` probe may exercise fake observers and codec
mechanics, but it must never issue a production bearer, fill a success-profile
slot, or establish GitHub origin.

## Outcome taxonomy

The healthy assertion success is only:

```text
CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED
```

The implementation must distinguish:

- definitive observation or validation failure;
- bounded absence, which is not proof that publication never happened;
- duplicate/identity/temporal ambiguity;
- GitHub transport or download outcome unknown;
- action failure/unknown branches supplied later by the frozen workflow; and
- durable commit success with failed readback, which remains reconciliation
  required and is never retried blindly.

No branch may translate `PUBLICATION_OUTCOME_UNKNOWN` or
`COMMITTED_READBACK_FAILED` into a healthy postcondition or an implicit retry.

## Durable recovery rule

There must be one complete stage-envelope commit, not competing partial
commits for the same stage identity. Before the create-only commit and again
after independent recovery, the bridge must validate:

- the exact current-run identity and authentic predecessor prefix;
- every required predecessor-read replay;
- the current-stage archive descriptor and bytes;
- the current-stage upload-postcondition descriptor and bytes;
- postcondition observation reconstruction and semantic binding;
- archive/postcondition cross-binding and prepared-member equality; and
- every other stage attachment codec required by that stage.

REGISTER support cannot be added to the current predecessor-read-only bridge
by pretending it has a predecessor replay. The bridge must be generalized
around complete stage profiles.

Process-local WeakSet/WeakMap brands are authority within one trusted runtime,
not durable authentication. Every recovered byte surface must therefore be
strictly decoded and cross-bound again.

## Falsification matrix

The implementation is not complete without negative tests for:

- forged/copied/stale/test-only authority or prepared capabilities;
- wrong-stage carrier and caller attempts to override any fixed selector;
- hostile proxies, accessors, sparse arrays, shared buffers, and mutation;
- concurrent assertion use and recreated-service permit replenishment;
- missing/duplicate/expired/cross-run/cross-head/temporally invalid artifacts;
- wrong current, predecessor, or later job states;
- non-distinct request IDs and non-monotonic observations;
- wrong observation count, order, kind, offsets, hashes, ETags, or receipts;
- re-query projection drift and run identity drift;
- download receipt, artifact ID, digest, length, redirect, or media-type drift;
- compressed, ZIP64, encrypted, timestamp/attribute-drifted, extra-member,
  path-trick, CRC, roster, member-hash, or member-byte violations;
- extra/missing manifest keys, noncanonical JSON, and self-hash mutation;
- cross-stage, cross-role, cross-run, or cross-envelope postcondition swaps;
- local golden postcondition relabeling;
- counterfeit or mutated durable recovery;
- definitive failure, unknown outcome, or interruption followed by retry; and
- gate-closed production composition performing any GitHub I/O.

## Dependency order after this freeze

1. Extract and test the shared root-private stage-artifact specification.
2. Implement the strict postcondition constants, codec, reconstruction, and
   mutation suite.
3. Implement the prepared-carrier capability, same-stage assertion permit,
   pure classification core, and fake-observer non-authorizing probe.
4. Implement the root-private Effect assertion shell and replay snapshot.
5. Run a bounded P0 feasibility proof for a shared external POSIX root from the
   fixed GitHub-hosted job topology. It must prove one authenticated namespace
   and device supporting hard-link CAS, fsync, and parent-directory durability;
   otherwise change the storage/runner architecture before broad stage work.
6. Generalize complete-stage profile commit/recovery, then close REGISTER,
   CONFIRM, and ADJUDICATE incrementally with real nested attachment bytes.
7. Close failure, interruption, unknown, and VOID profiles and implement the
   terminal fresh-bracket/rerun-invalidation finalizer.
8. Only then author and review the exact workflow, pin its raw bytes and one
   API path, freeze sources A/B, preregister, select future randomness, and
   dispatch attempt one.
9. Admit event 10 or a Q/B/R verdict only after every required byte is freshly
   recovered and the terminal bracket passes.

## Nonclaims and next-session instructions

- This checkpoint changes documentation/KG only; no runtime assertion or
  production postcondition is implemented yet.
- The production connector, three postcondition profile occurrences, complete
  48-slot profile, external durability, GitHub origin, and independent-process
  recovery remain open.
- A fake Layer or unit fixture is not production authority or GitHub evidence.
- A structurally valid `S2SArtifactEvidence` value is not provenance by itself.
- An action output artifact ID/digest is not independently observed evidence.
- A successful same-stage readback would not prove exactly-once publication.
- The v15 local golden receipts remain `TEST_ONLY_NON_AUTHORIZING` and have no
  adapter into this schema.
- No workflow, source freeze, preregistration, future pulse, dispatch,
  candidate, adjudication, event 10, or scientific verdict is created here.
- No entry belongs in `F1_R8_RESULTS_LOG.md`.

Resume by reading the constitution, v15 handoff/KG, this document, v16 KG, and
the `effect-ts-functional` skill. Preserve the unrelated dirty files
`src/hswm/experiments/continual_live.py` and
`tests/test_hswm_continual_live.py`. Keep all new code root-private and in
`src/hswm/effect-runtime/src/`; use `apply_patch`; verify focused tests, strict
TypeScript, full package tests/build/pack, KG chain, and `git diff --check`.
Use the Proxmox guardrail for any run expected to exceed five minutes or create
more than 100 MiB of scratch data.
