# HSWM SWM-0W-S2S stage-upload postcondition codec — next-session handoff

Date: 2026-08-23
Primary codec implementation: `1f45f4bad6907617cacac6525ea9edd8d9c7b6f4`
Historical-test compatibility follow-up: `5e1809a2019d57eb8e82ce0c6de18f67ef18815e`
Continuation KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v18.json`
Predecessor KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v17.json`
Frozen design: `docs/operations/HSWM_SWM0W_S2S_STAGE_UPLOAD_ASSERTION_DESIGN_NEXT_SESSION_2026-08-23.md`
Status: `STRICT NON-AUTHORIZING CODEC IMPLEMENTED / ASSERTION AND PROFILE OPEN / SCIENTIFICALLY UNJUDGED`

## Resume capsule

The first open gate from v17 is closed. Strict TypeScript/Effect now owns one
root-private stage-upload postcondition schema, deterministic carrier codec,
unknown-input validator, raw-observation reconstructor, canonical self-receipt,
and archive/prepared-member cross-binding for REGISTER, CONFIRM, and
ADJUDICATE.

This is deliberately a non-authorizing closure. The pure builder accepts only
`TEST_ONLY_NON_AUTHORIZING` permit evidence. Validation and reconstruction may
structurally recheck a serialized trusted-scope receipt for future durable
recovery, but they always return
`ValidatedNonAuthorizingStageUploadPostcondition`; serialized data never
issues or restores a bearer. No GitHub I/O, upload action, prepared-carrier
capability, one-use assertion permit, production Layer, or success-profile
occurrence was added.

Resume with the module-authentic prepared-carrier capability, one-use
same-stage assertion permit, and pure outcome classifier. Do not reinterpret
this codec or its fixtures as a production upload assertion, GitHub origin, or
scientific evidence.

## Canonical role and conceptual delta

HSWM remains the single token-native LLM-function macro-neural network defined
by `docs/canon/HSWM_CONSTITUTION_2026-08-20.md`. Its evolving hypergraph is the
living harness, world model, and continuous learner at once. The TypeScript
runtime, GitHub workflow, evidence store, repository KG, and MCP surfaces are
bounded projections and interfaces, not HSWM cognition.

Relative to v17:

- `H`: unchanged; no topology or living-harness evidence was added.
- `W`: unchanged; no learned semantic-weight result was added.
- `A`: unchanged; no activation or readout result was added.
- `F`: unchanged; no function-cell result or scientific verdict was added.
- `Pi`: narrowly advanced by closing the strict root-private,
  non-authorizing stage-upload postcondition schema, codec, reconstruction,
  and defensive cross-binding gate.
- outcome-bound causal-learning loop: not advanced.

The passing tests are evidence instruments for this bounded `Pi` contract.
They are not HSWM scientific progress by themselves.

## Implemented and verified

### Exact correlated manifest

`src/hswm/effect-runtime/src/s2s-stage-upload-postcondition.ts` implements the
frozen 37-key manifest family under schema:

```text
hswm-swm0w-s2s-stage-upload-postcondition/v1
```

The three stage variants correlate stage, role, producer job, artifact name,
archive reference, ordered archive validation, prepared members, and the exact
zero/one/two predecessor identity tuple:

| Stage | Role | Job | Artifact | Predecessors | Archive cap |
| --- | --- | --- | --- | ---: | ---: |
| REGISTER | REGISTRATION | register | s2s-registration | 0 | 4 MiB |
| CONFIRM | CANDIDATE | confirm | s2s-candidate | 1 | 64 MiB |
| ADJUDICATE | ADJUDICATION | adjudicate | s2s-adjudication | 2 | 4 MiB |

The fixed claims remain exact:

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

`PRODUCTION_INTENDED` identifies the frozen representation. It does not prove
that a production authority, GitHub run, upload, or profile occurrence exists.

### Deterministic carrier and observation closure

The representation remains:

```text
STORED_ZIP_COMPACT_MANIFEST_CONTIGUOUS_OBSERVATIONS_CURRENT_STAGE_ARCHIVE_REFERENCE
```

The deterministic stored ZIP contains exactly, in order:

```text
manifest.json
observations.bin
```

The implemented bounds are the frozen bounds, not widened profile limits:

```text
manifest maximum = 1,048,576 bytes
raw GitHub JSON body maximum = 1,048,576 bytes each
successful lookup ordinal = 1 | 2 | 3
observation count = 7 | 9 | 11
observation blob maximum = 11,534,336 bytes
stored-ZIP framing = 264 bytes
postcondition carrier maximum = 12,583,176 bytes
success-profile occurrence maximum = 16,777,216 bytes
```

Every compact observation descriptor binds its ordinal, phase, kind,
contiguous offset, byte length, raw-body SHA-256, observation time, request ID,
ETag, projection SHA-256, and receipt SHA-256. Reconstruction reparses every
raw body and recomputes the trusted projection and receipt before semantic
validation. Alternate valid ZIP orderings or dialects are rejected unless
they reproduce the exact deterministic stored representation.

### Same-stage structural semantics

The codec independently checks the exact current run/head and attempt-one job
roster represented by its supplied raw observations. REGISTER requires the
register job in progress, an empty predecessor tuple, and both later fixed jobs
not started. CONFIRM requires one successfully completed predecessor;
ADJUDICATE requires two successfully completed predecessors in order. The
current producer remains in progress with null conclusion, and later jobs must
remain inactive.

Artifact lookup admits at most three fixed-name list observations. Earlier
attempts must contain no matching artifact and the successful attempt exactly
one. The selected artifact must be current-run/current-head, unexpired, and
created no earlier than the current job start and no later than the successful
observation. Fresh artifact requery, download receipt, API digest, archive
length/hash, exact ZIP dialect, exact ordered member roster, member CRC/hash,
and member bytes are revalidated.

`archive_reference` is recomputed from the recovered current-stage archive.
`archive_validation` is recomputed from the ZIP. `prepared_members` is
independently snapshotted from the caller-supplied mechanics fixture, and its
member bytes must equal the recovered archive bytes exactly. This structural
tuple is not the still-open module-authentic prepared-carrier capability.

### Authority boundary and functional shape

The codec is a pure functional core:

- unknown-input builders and validators return `Either` with one tagged error
  family;
- Effect wrappers are lazy and add no hidden I/O;
- raw bytes and canonical values are defensively snapshotted;
- hostile proxies, accessors, sparse/exotic byte surfaces, shared buffers, and
  mutation are rejected or isolated without invoking hostile traps;
- returned evidence is deeply frozen and byte readers return fresh copies;
- the test-only builder refuses a forged
  `TRUSTED_SINGLE_MODULE_CURRENT_JOB` permit claim; and
- structural recovery of a future trusted-scope receipt remains explicitly
  non-authorizing.

The generalized current-run evidence validator now admits the stage-correlated
zero/one/two predecessor tuples. Its predecessor-read compatibility wrapper
still rejects REGISTER, so this slice does not counterfeit a registration
predecessor read. The new codec and validator remain absent from the package
root.

Pure scalar limits moved to `s2s-resource-limits.ts`. Existing live GitHub and
Python modules retain their prior exports and numeric values, while pure
contract modules no longer import live adapters merely for those constants.

### Verification

At primary code checkpoint `1f45f4b` plus the source-invariant compatibility
follow-up `5e1809a`:

```text
npm run check: PASS
focused stage-upload postcondition tests: 19/19 PASS
Vitest: 26/26 files, 310/310 tests PASS
npm run build: PASS
npm pack --dry-run: PASS, 208 files, approximately 3.4 MB unpacked
v1-v18 handoff/KG chain: 87/87 PASS
git diff --check: PASS
```

The focused suite covers all three stages across all three successful lookup
ordinals; deterministic build/validate/reconstruct round trips; the exact
37-key manifest, counts, caps, and self-hash; deep freezing, defensive copies,
and Effect laziness; hostile unknown inputs; projection reconstruction without
truncating 65-entry arrays; observation topology and receipt drift; carrier
dialect/order drift; cross-stage, job-roster, artifact, requery, download,
archive-reference, and prepared-member drift; reused request IDs and
nonmonotonic observations; the exact carrier ceiling; test-only golden
rejection; forged trusted-build rejection; non-authorizing structural recovery;
and the REGISTER generic-versus-predecessor-read boundary.

No live GitHub run, external upload, remote KG write, or research result was
produced. No entry belongs in `F1_R8_RESULTS_LOG.md`.

## Exact nonclaims

- This slice implements a strict production-intended representation codec, not
  a production upload assertion or connector.
- No module-authentic prepared-current-stage carrier capability exists.
- No module-authentic one-use same-stage assertion permit or bearer exists.
- No live GitHub observer/assertion shell, bounded settling schedule, outcome
  classifier, interruption closure, or reconciliation program exists.
- No pinned workflow-owned `actions/upload-artifact` step was authored or run.
- Uploader-returned artifact identity or digest is not used as evidence.
- Structurally valid current-run, permit, observation, artifact, or
  postcondition data is not provenance or authority by itself.
- Structural recovery of serialized trusted-scope permit evidence does not
  restore process-local authority.
- No historical artifact uniqueness, exactly-once publication, or
  cross-worker/module/process/durable replay prevention is claimed.
- No production REGISTER, CONFIRM, or ADJUDICATE upload-postcondition profile
  occurrence was filled.
- No complete stage profile was committed or independently recovered.
- No external shared POSIX feasibility, deployment, authenticated durable
  root, or independent-process restart recovery was observed.
- The production Layer remains gate-closed while workflow source bytes are
  open.
- Workflow bytes, exact API-path freeze, source A/B freeze, preregistration,
  future randomness, and confirmatory dispatch remain absent.
- Genuine current-run and stage-artifact capabilities remain unissued.
- GitHub origin, terminal event 10, and a Q/B/R scientific verdict remain
  absent.
- The v15 golden postcondition remains `TEST_ONLY_NON_AUTHORIZING` and has no
  adapter into this schema.
- No `H`, `W`, `A`, or `F` result changed, and the outcome-bound causal-learning
  loop did not advance.

## Next-session execution order

1. Read the constitution, v16 design, v17 handoff/KG, this handoff, the v18 KG,
   and the `effect-ts-functional` skill. Preserve the two unrelated dirty
   continual-live paths listed below.
2. Implement the module-authentic prepared-carrier capability and one-use
   same-stage assertion permit, plus the pure typed outcome classifier and a
   separately named fake-observer non-authorizing probe.
3. Implement the root-private Effect assertion shell and replay snapshot. Keep
   all polling, settling, download, deadlines, interruption, and
   unknown-outcome reconciliation bounded. Keep production Layer composition
   gate-closed while workflow bytes remain open.
4. Run the bounded P0 shared-external-POSIX feasibility proof before broad
   stage/profile expansion. Prove one authenticated namespace/device with
   create-only hard-link CAS, fsync, and parent-directory durability, or change
   the storage/runner architecture.
5. Generalize one complete create-only stage-profile commit and independent
   recovery path for REGISTER, CONFIRM, and ADJUDICATE with the real nested
   archive and postcondition bytes. Do not add competing partial commits.
6. Close failure, interruption, unknown, and VOID profiles and implement the
   terminal fresh-bracket/rerun-invalidation finalizer.
7. Only then author and review the exact workflow, pin its raw bytes and one API
   path, freeze sources A/B, preregister, select future randomness, and dispatch
   attempt one.
8. Admit event 10 or a Q/B/R verdict only after every required byte is freshly
   recovered and the terminal bracket passes.

## Protected unrelated worktree paths

These user-owned changes predated this slice and are not part of code checkpoint
`1f45f4b`:

```text
src/hswm/experiments/continual_live.py
tests/test_hswm_continual_live.py
```
