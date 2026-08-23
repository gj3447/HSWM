# HSWM SWM-0W-S2S shared stage-artifact specification — next-session handoff

Date: 2026-08-23
Current code checkpoint: `242ff8a86ab47009a484354fd4e82737723c8a5b`
Primary implementation checkpoint: `6c63ea77559da9ca9725eb99ac7e4c0241c5af3b`
Continuation KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v17.json`
Predecessor design: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v16.json`
Status: `SHARED POLICY SLICE IMPLEMENTED / CODEC AND ASSERTION OPEN / SCIENTIFICALLY UNJUDGED`

## Resume capsule

The first implementation step from the v16 upload-assertion design is complete.
Strict TypeScript now owns one root-private, deeply frozen, stage-indexed
`S2S_STAGE_ARTIFACT_SPECS` value for REGISTER, CONFIRM, and ADJUDICATE. Existing
live predecessor readback and predecessor replay source-reference code consume
that value instead of maintaining private copies. Stage-specific literal
correlations are retained by TypeScript, so those replay references no longer
need casts.

The same slice freezes only the upload-postcondition identifier,
representation, member names, observation counts, and exact byte budgets. It
does not implement an Effect `Schema`, manifest codec, unknown-input decoder,
raw-observation reconstruction, self-receipt, archive cross-binding, uploader,
or same-stage assertion. None of the three production postcondition profile
occurrences is filled.

Resume from the strict postcondition codec and hostile reconstruction tests.
Do not skip forward to workflow authoring, preregistration, a live run, or a
scientific verdict.

## Canonical role and conceptual delta

HSWM remains the single token-native LLM-function macro-neural network defined
by `docs/canon/HSWM_CONSTITUTION_2026-08-20.md`. Its evolving hypergraph is the
living harness, world model, and continuous learner at once. The TypeScript
runtime, repository KG, GitHub workflow, evidence store, and MCP surfaces are
bounded projections and interfaces, not HSWM cognition.

Relative to v16:

- `H`: unchanged; no topology or living-harness evidence was added.
- `W`: unchanged; no learned semantic-weight result was added.
- `A`: unchanged; no activation or readout result was added.
- `F`: unchanged; no function-cell or scientific verdict was added.
- `Pi`: narrowly advanced by implementing one internal stage-artifact policy
  projection and the postcondition representation/byte-budget skeleton.
- outcome-bound causal-learning loop: not advanced.

The 291 passing Effect tests are evidence instruments for this narrow `Pi`
contract. They are not HSWM scientific progress by themselves.

## Implemented and verified

### Root-private stage specification

`src/hswm/effect-runtime/src/s2s-stage-artifact-spec.ts` now binds, per stage:

- stage, artifact role, job ID/name, and fixed artifact name;
- archive and postcondition logical names and profile roles;
- carrier and postcondition schema identifiers;
- archive and expanded-byte ceilings;
- exact ordered member names and member ceilings; and
- the distinct exact postcondition carrier ceiling and profile-slot ceiling.

The important cap distinction is explicit:

```text
postconditionCarrierMaximumBytes = 12,583,176
postconditionProfileMaximumBytes = 16,777,216
```

The 16 MiB profile slot is not permission for the future codec to emit more
than 12,583,176 bytes.

The workflow stage-contract constant now uses `satisfies` rather than a
widening declaration. This preserves REGISTER/CONFIRM/ADJUDICATE literal
correlations through the shared specification. The package root exports none
of the new specification or budget symbols.

### Postcondition representation and budget skeleton

`src/hswm/effect-runtime/src/s2s-stage-upload-postcondition-contract.ts`
freezes:

```text
schema identifier = hswm-swm0w-s2s-stage-upload-postcondition/v1
representation = STORED_ZIP_COMPACT_MANIFEST_CONTIGUOUS_OBSERVATIONS_CURRENT_STAGE_ARCHIVE_REFERENCE
members = manifest.json, observations.bin
successful lookup ordinal = 1 | 2 | 3
observation count = 7 | 9 | 11
manifest maximum = 1,048,576 bytes
observation blob maximum = 11,534,336 bytes
stored-ZIP framing = 264 bytes
carrier maximum = 12,583,176 bytes
```

The observation-count function is a literal lookup with no result cast. A
module-load invariant fails closed if the fixed framing or total drifts.

### Consumer migration

- `s2s-live-artifact.ts` derives all three read policies from the shared map.
- `s2s-stage-artifact-read-replay.ts` derives registration and candidate source
  references from the shared map without literal assertions.
- Existing evidence-profile descriptors remain separately checked for exact
  equality. They have not yet been structurally generated from the map.

### Verification

At code checkpoint `6c63ea7`:

```text
npm run check: PASS
Vitest: 25 files, 291 tests PASS
npm run build: PASS
npm pack --dry-run: PASS (198 files, about 3.1 MB unpacked)
focused post-hardening check: 33/33 PASS
v1 through v17 handoff/KG chain: 81/81 PASS
git diff --check: PASS
```

Follow-up `242ff8a` retained a truthful legacy source-ownership marker after the
adjudication cap moved behind the shared specification; it changed no runtime
behavior.

No live GitHub run, external upload, remote KG write, or research result was
produced. No entry belongs in `F1_R8_RESULTS_LOG.md`.

## Exact nonclaims

- The new file named `*-contract.ts` is a representation and budget skeleton,
  not a production postcondition codec.
- No Effect `Schema`, exact manifest shape, strict decoder, builder, validator,
  raw-observation reconstructor, or self-hash exists for this postcondition.
- No prepared-carrier capability or upload-specific assertion permit exists.
- No uploader output is accepted as evidence and no uploader is implemented in
  the Effect runtime.
- No same-stage artifact was independently listed, requeried, downloaded, or
  reconciled by this slice.
- No complete REGISTER, CONFIRM, or ADJUDICATE profile is committed or recovered.
- The three production upload-postcondition occurrences remain unfilled.
- No external shared POSIX feasibility, deployment, authentication, or
  independent-process recovery has been observed.
- Workflow bytes and preregistration are absent; genuine current-run and stage
  capabilities remain unissued.
- GitHub origin, event 10, and a Q/B/R scientific verdict remain absent.
- The v15 golden codec remains test-only and cannot be relabelled as production.

## Next-session execution order

1. Read the constitution, this handoff, v16, v17, and the
   `effect-ts-functional` skill. Preserve the two unrelated dirty continual-live
   paths listed below.
2. Implement `s2s-stage-upload-postcondition.ts` as a strict functional core:
   exact Effect schemas, exact-key manifest parsing, canonical self-receipt,
   deterministic two-member stored ZIP build/validate, raw-observation
   reconstruction, and archive/prepared-member cross-binding.
3. Reuse or factor only the small pure compact-observation ZIP mechanics needed
   by both read replay and upload postconditions. Keep semantic schemas distinct
   and avoid making pure contract code depend on live adapters merely for scalar
   limits.
4. Add hostile unknown-input and mutation tests before adding any live shell.
   Reject accessor/proxy inputs without invoking getters, noncanonical JSON,
   wrong observation topology/offset/hash/receipt, ZIP dialect drift, member
   substitution, archive-reference drift, and the test-only golden schema.
5. Only after the codec is closed, implement the module-authentic prepared
   carrier capability, one-use same-stage assertion permit, and pure
   classification core. Keep production Layer construction gate-closed while
   workflow source bytes are open.
6. Run the bounded shared-POSIX feasibility proof before expanding complete
   stage programs. Then generalize one complete-stage create-only commit and
   recovery path; do not add competing partial commits.
7. Workflow freeze, preregistration, future randomness, dispatch, event 10, and
   scientific judgment remain downstream gates.

## Protected unrelated worktree paths

These user-owned changes existed before this slice and were not staged or
modified by this work:

```text
src/hswm/experiments/continual_live.py
tests/test_hswm_continual_live.py
```

## Environment note

The stop hook repeatedly reported:

```text
/home/lagyeongjun/.orca/agent-hooks/codex-hook.sh: 76: Syntax error: Bad for loop variable
```

That hook is outside this repository and was not changed. It is not evidence of
an HSWM runtime or test failure.
