# HSWM SWM-0W-S2S golden vertical-composition design handoff

Date: 2026-08-23

Repository checkpoint before this handoff: `d2d727e828fcb1daa462d5ce8a1a1a08594768af`

Current implementation checkpoint: `8d9f254c11176a194f74610cfac422dfa67aae08`

V13 continuation predecessor:
[`HSWM_SWM0W_S2S_DURABLE_REPLAY_PROFILE_INTEGRATED_NEXT_SESSION_2026-08-23.md`](HSWM_SWM0W_S2S_DURABLE_REPLAY_PROFILE_INTEGRATED_NEXT_SESSION_2026-08-23.md)

Companion local KG projection:
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v14.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v14.json)

Authority: the strict TypeScript/Effect direction is `USER_PRIMARY`. The
component audit, profile classification, minimal composition, and implementation
order below are `SECONDARY_AI_PROPOSED` engineering claims. The scientific
verdict remains `UNJUDGED`.

Status: `BLOCKED_PRE_PREREG / GOLDEN_LOCAL_VERTICAL_DESIGN_FROZEN /
IMPLEMENTATION_NOT_STARTED / SCIENTIFIC_UNJUDGED`.

This is a design and continuation checkpoint. It adds no runtime implementation,
runs no confirmatory or golden-success numeric workload, and changes no scientific
claim. It supersedes v13 only as the next-session entrypoint. V1 through v13
remain immutable historical projections. The companion KG is a local repository
projection, not HSWM cognition, a remote KG publication, a preregistration, or a
scientific result.

## Direct answer: TypeScript, Effect, and the numeric oracle

The HSWM research control runtime is being developed strict TypeScript-first and
functionally with Effect v3:

- TypeScript `5.9.3`;
- Effect `3.22.1`;
- Node `24.13.0`;
- Vitest `3.2.7`.

The `effect-ts-functional` skill is actively applied to this work. In this
checkpoint it fixed the Effect-v3 API family, the functional-core/effect-shell
split, root-private composition, typed errors, `Context.Tag` service boundaries,
test `Layer`s, lazy execution, and public-export containment. The skill is an
authoring workflow; it is not a package dependency or an HSWM capability.

“TypeScript-based” does not mean translating the already checked Python/NumPy
numeric oracle without evidence. The intended boundary is:

```text
strict TypeScript + Effect
  owns orchestration, authority, resources, failure, evidence, upload/readback
                    |
                    v
bounded Python/NumPy numeric function cell
  owns deterministic SWM-0W-S2S confirm/adjudicate arithmetic only
```

The Python process owns no Git/GitHub authority, clock, beacon selection,
artifact publication, or verdict. It is invoked through the existing
`S2SPythonNumericExecutor` Effect service, with its executable and source closure
pinned and its outputs rebound into typed evidence. The unused older
`PythonNumericOracle` abstraction must not be revived as a second orchestration
model.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
Its evolving hypergraph remains the one living harness, world model, and
continuous learner. The Effect runtime and repository KG remain bounded
control/evidence projections around that entity.

- `H`: unchanged. No hypergraph topology, memory, or world-state update ran.
- `W`: unchanged. No role-aware semantic weight or causal credit was learned.
- `A`: unchanged. No activation, coalition, or readout efficacy was measured.
- `F`: unchanged. No golden-success or confirmatory numeric result ran.
- `Π`: unchanged by this documentation checkpoint. The next local engineering
  slice is now more precisely bounded, but it is not implemented.

The outcome-bound causal-learning loop did not advance. Repository inspection
and tests are engineering instruments, not evidence that HSWM learned or that
SWM-0W-S2S passed.

## Audited existing numeric path

Every low-level component required to run a public golden numeric candidate and
then adjudicate that exact candidate already exists. The shortest intended path
is:

```text
loadS2SAdoptedProtocolConfigAsset
  -> buildPythonNumericConfirmRequest(public golden seed, adopted config)
  -> S2SPythonGoldenVerifier.verify
  -> exact-compare verifier and executor runtime-source identity receipts
  -> S2SPythonNumericExecutor.confirm
  -> bindS2SPythonExecutionEvidence(confirm)
  -> explicitly test-only golden candidate archive + two local readbacks
  -> S2SPythonNumericExecutor.adjudicate(second readback candidate bytes)
  -> makeOpaqueNumericFile(adjudication)
  -> projectOpaqueNumericAdjudication
     -> VOID: typed terminal, no adjudication evidence/carrier/profile
     -> non-VOID: bindS2SPythonExecutionEvidence(adjudicate)
  -> explicitly test-only golden adjudication archive + local readback
```

The fixed public test material is:

- external seed:
  `552e51d2ff75cb7c5df5b55a166aba12a277c2813bbdd69bc825286e7c26b6f0`;
- confirm-request self hash:
  `16e4965054165863add0395397cbf3d68d1f3d472b7fc303e40056855368b1d1`;
- confirm-request document hash:
  `294eb438fe042238bbe725d0473765f3634eb57876e5cae4807915db66034237`;
- adopted protocol-config document hash:
  `315dad65a8882c4b7c5fb73d295df28b58b0696e25b1b790a342b40ced8d10c4`.

The seed is explicitly `CROSS_LANGUAGE_TEST_VECTOR_NOT_CONFIRMATORY_EVIDENCE`.
It requires no future beacon, preregistration, or GitHub authority. The actual
successful 60-cell confirm/adjudicate workload has not yet been executed through
the Effect composition. Existing live executor tests exercise the real process
with rejected inputs and exercise the golden verifier, but do not produce a
successful candidate and adjudication.

If the golden adjudication projects `VOID`, that is a valid dry-run falsifier.
The program must return a typed non-authorizing `VOID` result and must not force a
healthy-success envelope or fabricate a three-stage success chain.

## Audited semantic type gap

The first draft of this handoff assumed the existing production carrier
builders could consume the local non-authorizing readback. That is false and is
now an explicit P0 design finding.

`prepareS2SRegistrationCarrier`, `prepareS2SCandidateCarrier`, and
`prepareS2SAdjudicationCarrier` require the production confirmatory-event union
and `S2SArtifactEvidence`. Those values semantically include preregistration,
future-beacon, source/registration commits, GitHub observation and download
schemas, GitHub artifact IDs, retention, and API digests. A local test receipt
cannot honestly inhabit those types. The v13 regression uses synthetic
production-shaped values only as a unit-test fixture; they must not be promoted
into persisted dry-run evidence.

Therefore the first golden implementation must:

- not call the three `prepareS2S*Carrier` production builders;
- not synthesize confirmatory lifecycle events or `S2SArtifactEvidence`;
- not place local golden bytes into the healthy-success profiles;
- not commit the local golden result through `S2SDurableEvidenceFileStore`;
- define a separately versioned `TEST_ONLY_NON_AUTHORIZING` numeric artifact
  and readback-postcondition contract, and provide no adapter or call site that
  projects it into a production stage carrier, event, or profile.

This test-only artifact contract is an engineering harness for the
Effect/Python/upload seam, not a second confirmatory orchestration model. It has
only `GOLDEN_CANDIDATE` and `GOLDEN_ADJUDICATION` roles and no registration,
beacon, GitHub, workflow, event, profile, or verdict fields. The production
three-stage path remains unchanged and open until it has genuine authority
values or a separately reviewed semantic connector that does not counterfeit
them.

## Healthy-success attachment inventory

The fixed rosters contain 48 stage-slot occurrences:

| Stage | Slot occurrences |
|---|---:|
| `REGISTER` | 13 |
| `CONFIRM` | 17 |
| `ADJUDICATE` | 18 |
| Total | 48 |

The audit classified them by the strongest current repository implementation:

| Class | Count | Meaning |
|---|---:|---|
| `CONSTRUCT_AND_VALIDATE` | 20 | Exact attachment bytes can be produced/acquired and independently validated after recovery. |
| `SEMANTIC_CORE_NO_ATTACHMENT_CODEC` | 19 | A relevant producer or semantic validator exists, but the profile attachment lacks its own byte codec/replay validator. |
| `MISSING_CARRIER_OR_SOURCE` | 9 | Only the roster descriptor or partial primitives exist; the required carrier/source does not. |

The 20 construct-and-validate occurrences are the three current-invocation event
bytes, adopted protocol config, pilot adoption, preregistration, the three stage
archives, confirm request, the four predecessor replay slots, both Python RSS
receipts, both drand raw pulses, and both drand verification receipts.

The 19 codec-open occurrences are the three current-invocation evidence objects,
three current-run replay snapshots, registration commit evidence, operational
policy, workflow contract, the two Python execution objects, two Python
invocation objects, two Python runtime objects, two drand fixtures, and two drand
requests.

The nine missing occurrences are registration source ZIP, workflow source bytes,
three stage upload-postcondition ZIPs, two Python golden-replay ZIPs, and two drand
execution objects.

The top-level profile validator currently checks the exact roster, descriptors,
media types, and byte caps. It does not prove these nested semantics. The v13
integration intentionally fills non-replay slots with one-byte sentinels.

Accordingly:

- the next slice may honestly be called a
  `TEST_ONLY_NON_AUTHORIZING_GOLDEN_VERTICAL_REPLAY`;
- it may replace only the slots it actually produces and validates;
- it must not claim `HEALTHY_SUCCESS_PROFILE_COMPLETE`;
- a later complete-profile gate requires all 48 occurrences to contain real
  bytes and to pass their nested validators after durable recovery, including a
  one-byte-mutation failure per schema family.

## Mandatory upload/readback boundary

Two upload-related boundaries must remain separate.

### Production stage-local mandatory upload/readback

For each stage, the stage program must derive the fixed artifact name and role,
publish the exact deterministic carrier, distrust the publish return value, and
independently read it back. It must revalidate publication key, digest, byte
length, strict ZIP dialect, exact member roster, member hashes, and member bytes.
It then writes both the archive and a bound upload-postcondition ZIP into the
stage profile and revalidates them after evidence-store recovery.

This production boundary remains open. The local golden harness must not reuse
its schema or claim to close it.

### Test-only golden numeric upload/readback

The next slice exercises the same mechanical risks without claiming production
semantics: fixed internal numeric-artifact role, deterministic bytes,
create-only publication, independent store read, hash/length/roster/member-byte
validation, a typed postcondition, and fresh-Layer recovery. Its schema and
receipt must say `TEST_ONLY_NON_AUTHORIZING / LOCAL_TEST_LAYER`, must not contain
a GitHub artifact ID, and must never be supplied or relabeled as a production
carrier or profile attachment by the harness. The current top-level
success-profile validator checks descriptors and caps, not nested bytes, so this
checkpoint does not claim that it would reject a maliciously relabeled test ZIP.

### Production terminal finalizer

The later production finalizer must freshly reobserve attempt-one run/jobs,
runs-for-registration-B, artifact metadata, and downloads immediately before
event 10, invalidate reruns, and only then publish a create-only verdict. That
boundary remains entirely open and is not part of the local golden slice.

The existing read-only GitHub observer cannot upload. The generic
`ConfirmatoryArtifactStore` skeleton is also not suitable: it accepts
caller-selected names and split identity/digest arguments, returns `unknown`,
and does not bind publish to readback. It should remain unused rather than being
silently treated as the missing implementation.

## Frozen next implementation slice

The next session should add one small, root-private functional vertical path.
Names may change only if repository conventions require it; the authority and
dataflow must not.

### Pure cores

1. `s2s-test-only-golden-upload.ts`
   - define a distinct
     `hswm-swm0w-s2s-test-only-golden-upload-postcondition/v1` schema;
   - allow only `GOLDEN_CANDIDATE` and `GOLDEN_ADJUDICATION` roles, with fixed
     internal names;
   - bind a local publication key, `CREATED` disposition, archive and readback
     hash/length, exact member name/hash/length roster, equality result, and
     `TEST_ONLY_NON_AUTHORIZING / LOCAL_TEST_LAYER` classification;
   - encode one canonical `postcondition.json` member with the existing
     deterministic stored-ZIP writer;
   - reconstruct unknown input and fail on every cross-binding mismatch.

2. Reuse, without duplicating, only the semantically compatible pure cores:
   `buildPythonNumericConfirmRequest`, `bindS2SPythonExecutionEvidence`,
   `makeOpaqueNumericFile`, `buildS2SStoredZip`, `validateS2SArtifactZip`, and
   `projectOpaqueNumericAdjudication`. Do not call the production job-sequence,
   confirmatory-event, success-profile, v13 replay-profile, or durable-evidence
   commit APIs from this harness.

### Effect shell

3. `s2s-test-only-golden-artifact-store.ts`
   - expose a root-private `Context.Tag` with only
     `publishGoldenArtifact(role, exactMembers)` and
     `readBackGoldenArtifact(moduleIssuedReceipt)`;
   - provide a test-only create-once file `Layer` whose constructor requires an
     explicit caller-owned temporary root;
   - snapshot inputs, derive all names internally, and issue a module-authentic
     local receipt;
   - perform no implicit publish retry;
   - read from the store again rather than returning publish-time bytes;
   - prove fresh-Layer recovery by building a new Layer over that same explicit
     root; an in-memory-only backing is not acceptable;
   - return typed failures at least for `PUBLISH_FAILED`,
     `PUBLICATION_OUTCOME_UNKNOWN`, `READBACK_FAILED`, `READBACK_MISMATCH`,
     `POSTCONDITION_INVALID`, `RECOVERY_MISMATCH`, and
     `CREATE_ONLY_CONFLICT`.

4. `s2s-golden-numeric-dry-run.ts`
   - expose one root-private lazy `runS2SGoldenNumericDryRun` Effect;
   - require `S2SPythonGoldenVerifier`, `S2SPythonNumericExecutor`, the new local
     golden-artifact service, and no production authority service;
   - use only the package-owned adopted config and fixed public golden seed;
   - require the golden verification runtime-source receipt to exact-match the
     numeric executor runtime-source receipt before invoking `confirm`;
   - bind confirm evidence before publishing the candidate;
   - publish the test-only candidate artifact, perform two independent
     readbacks, exact-compare them, and feed only the second validated numeric
     member to adjudication;
   - call `projectOpaqueNumericAdjudication` before the production adjudication
     evidence binder. If it returns `NUMERIC_OUTCOME_VOID`, return a frozen typed
     terminal summary containing only validated executor input/output/runtime/RSS
     hashes; do not bind production adjudication evidence and do not publish an
     adjudication artifact;
   - on a non-VOID projection, bind adjudication execution evidence, publish and
     independently read back the test-only adjudication artifact;
   - recover the test-only store with a fresh Layer over the same caller-owned
     temporary root and reconstruct every artifact and postcondition byte
     produced by this harness;
   - return only a frozen test-only summary or typed `VOID`; never a production
     event, success profile, durable evidence envelope, event 10, or scientific
     verdict.

All new constructors, receipt brands, errors, Layers, and the composition
entrypoint remain absent from `src/index.ts`.

## Verification order for the next session

1. Add pure postcondition round-trip, strict-input, cross-binding, and one-byte
   mutation tests.
2. Add service tests for create-only conflict, failed publication, unknown
   publication, no retry, independent readback, and readback mismatch.
3. Compose the dry run with fake Effect services first and prove lazy execution,
   verifier/executor runtime-identity mismatch rejection, exact call order,
   defensive byte copies, immediate `VOID` termination, fresh recovery,
   absence of any production projection adapter or call, and public-root
   containment.
4. Run the normal strict TypeScript check, Vitest package, build, package dry run,
   Python KG-chain tests, and `git diff --check`.
5. Run one real successful golden composition only as an opt-in heavy job through
   `proxmox-scratch run` with a timeout no greater than 7,200 seconds. Do not put
   the approximately 60-cell workload in the default test suite. Preserve only a
   small hash/telemetry receipt if it is a material engineering result.
6. After that local slice passes, separately design the production semantic
   connector. It must consume genuine confirmatory authority; local receipts
   cannot be cast or projected into production events or artifact evidence.
7. Only after that connector is reviewed should work resume on the remaining 28
   profile occurrences. Do not describe the profile as complete before all 48
   are real and recovery-validated.

## Explicit nonclaims

- A local artifact key is not a GitHub artifact ID.
- A local deterministic ZIP is not a GitHub-origin archive.
- A temp or in-memory Layer is not external shared durability or cross-process
  authentication.
- One source-level publish call and no retry do not prove exactly-once external
  publication.
- The local postcondition does not implement the production terminal finalizer.
- The test-only golden artifact cannot inhabit `S2SArtifactEvidence`, a
  confirmatory event, or a production carrier without fabrication; the harness
  provides no such projection or call site.
- The shallow success-profile validator is not claimed to reject a maliciously
  relabeled test-only ZIP; containment depends on the root-private harness never
  constructing or passing that relabeling.
- The harness neither replaces nor duplicates the production confirmatory
  lifecycle; it only falsifies the numeric-process and local-store seam.
- A public golden seed is not future randomness and cannot authorize a
  confirmatory run.
- A successful golden candidate/adjudication is still
  `NUMERIC_CANDIDATE_ONLY_UNJUDGED`.
- Partial real attachment substitution does not complete a healthy-success
  profile.
- The local repository KG is not HSWM cognition or a remote KG mutation.
- This checkpoint creates no source freeze, preregistration, future beacon,
  dispatch, candidate, adjudication, event 10, or scientific verdict.

The broad flags `mandatory_upload_postconditions_implemented`,
`closed_stage_programs_implemented`, `github_origin_established`, and
`event_10_composed` must remain false after the narrow local slice. A later KG
may add only a scoped fact such as
`local_test_only_upload_readback_vertical_slice_implemented: true` when that
exact implementation has passed.

## Protected unrelated work

Do not edit, stage, or restore these pre-existing user changes:

- `src/hswm/experiments/continual_live.py`;
- `tests/test_hswm_continual_live.py`.

## Resume checks

```sh
git status --short
git log -4 --oneline
cd src/hswm/effect-runtime
npm run verify
cd ../../..
uv run pytest -q tests/test_hswm_swm0w_s2s_effect_handoff*.py
```

The first implementation action next session is the distinct test-only golden
artifact/postcondition schema with no production projection adapter. The first
store action is a create-only file Layer over an explicit caller-owned temporary
root. The first composition action is verifier/executor runtime identity binding
under fake services. The real heavy golden run comes only after these boundaries
are locally falsifiable.
