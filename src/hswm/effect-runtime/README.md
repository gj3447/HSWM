# HSWM Effect runtime

> **Ontology boundary (2026-08-26):** `hswm-core-ontology*.ts` and the fixed
> `H/W/A/F/Pi` responsibility bundle are retained v1 compatibility artifacts.
> They are not the current HSWM ontology and must not be used as a fixed owner
> registry for new canonical writes. The current target requires exactly one
> schema-relative responsibility owner per admitted canonical atom. The generic
> v2 reference kernel, content-bound facade, predecessor-bound durable journal
> facade, pure typed transition-evidence contract, and local-head-relative
> current-state eligibility checker are now implemented. A separate
> TypeScript-to-Lean boundary now proves in Lean and reports in TypeScript why
> those v1 artifacts cannot yet refine the canonical `Learn` relation. An
> owner-bound outcome contract now separates observation responsibility from
> revision-support judgment responsibility without claiming truth or causal
> credit. The
> content-bound facade alone still has
> process-local state; the newer file-backed durable runtime can reconstruct one
> local linear state-and-receipt lineage from exact immutable records. This is
> not a production canonical store, distributed consensus, canonical/global Permit,
> migration system, learning result, or scientific verdict.
> See the
> [single-owner canon](../../../docs/canon/USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.md).

This private package is the TypeScript/Effect production-runtime seed for
HSWM. It contains two distinct bounded engineering slices: the existing scalar
outcome-credit transaction for an already eligible trajectory, and a
package-internal role-aware T16 forward projection over checked-in Python
learned-archive parameter bytes. They are not yet composed or publicly
exported as one semantic-weight abstraction.

The current v2 boundary is intentionally small:

- `canonical-atom-v2-schema.ts` defines strict Effect Schema ingress for an
  open owner/kind registry, fork-safe atom keys, content descriptors, typed
  role-bearing references, transition proposals, and deep immutable snapshots.
- `canonical-atom-v2-domain.ts` validates schemas and complete prior states,
  rejects implicit migration and unsealed trace claims, and implements the pure
  append-only atom/relation/revision transition. It does not implement learning.
- `canonical-atom-v2-runtime.ts` separates owner, actor claim, and an opaque
  reference-layer grant; atomically commits state plus one receipt with
  `Ref.modify`. A matched grant is explicitly not claimed to be a canonical,
  revocation-aware permit.
- `canonical-atom-v2-json.ts` defines a bounded duplicate-aware, safe-integer
  canonical JSON domain distinct from the historical S2S codecs.
- `canonical-atom-v2-content*.ts` bind exact raw payload bytes, canonical schema
  bytes and canonical atom metadata envelopes. The local POSIX adapter uses
  create-only publication, file and directory fsync, immutable readback and one
  durable schema-version binding.
- `canonical-atom-v2-content-runtime.ts` verifies authorization, pure-domain
  validity and every required byte before the process-local `Ref` commit. Its
  receipt says `CONTENT_ONLY_STATE_JOURNAL_NOT_DURABLE`; concurrent losers may
  leave unreferenced immutable blobs but never an admitted atom or receipt.
- `canonical-atom-v2-state-journal*.ts` define exact canonical genesis/commit
  records and a root-private Effect store. The local POSIX adapter publishes a
  content-addressed record object and one create-only fixed revision slot. Its
  one-winner property assumes the observed slot remains intact; it is not an
  external anti-rollback witness. A package-root-private, internal test-only
  seam interrupts 14 logical publication checkpoints and verifies fresh
  replay; it is absent from the package-root API and is not a physical
  power-loss simulator. A second Layer-local seam injects raw native-like
  link/fsync/readback errors to exercise typed retry and unknown-outcome
  branches. A test-only pre-link barrier drives distinct live processes into
  the same-prefix fixed-slot hard-link competition. Neither seam is production
  wiring, distributed consensus, or an OS/device fault experiment.
- `canonical-atom-v2-durable-runtime.ts` treats that journal—not a mutable
  cache—as the recovery truth. Every snapshot, history read and submit replays
  the chain, verifies schema/payload/envelope content and recomputes each pure
  transition and receipt before exposing state.
- `canonical-atom-v2-rdf-projection.ts` compiles one strictly self-consistent,
  caller-supplied canonical schema/state/journal-tail bundle into a read-only
  manifest and a role-preserving, blank-node-free RDF 1.1 N-Quads dataset.
  Exact recompilation rejects source drift and tampering. This is a local
  deterministic profile, not a live durable-recovery attestation, executable
  compiler-artifact binding, RDFC-1.0 result, SHACL or PROV-O conformance,
  canonical write path, cognition, causal learning, or efficacy.
- `canonical-atom-v2-transition-evidence.ts` gives authorization-decision,
  provenance, pre-outcome trajectory, reference-effect, outcome-observation and
  rejection/quarantine evidence separate strict record codecs plus one exact
  cross-binding bundle. Decision/trace keys are declared pre-existing reads,
  not self-written evidence; their actual state membership and whether the
  claimed predecessor is the current head still require a later resolver.
  Every authorization classification remains `NOT_PERMIT`; outcome
  independence remains declared rather than proved, and no issuer, evidence
  store, runtime admission or learning path is exported.
- `canonical-atom-v2-current-state-permit.ts` checks stable admitted Permit
  policy, authorization-decision, consent-decision and trajectory-contract
  records against exact schema/state/head evidence. Its pure checker only
  assesses caller-supplied snapshot evidence. Its public positive wrapper first
  compares that package with exactly one recovered durable-runtime snapshot;
  caller-supplied `evaluatedAt` still is not trusted “now”, and the local head
  remains neither anti-rollback proof nor a canonical/global Permit. The result
  is read-only, is not accepted by `submit`, and does not implement admission,
  external effects or learning. Bounded v1 does not permit a policy or candidate
  to write any permission-bearing kind, and no admitted permission-bearing
  logical lineage can be self-revised; only ordinary policy-approved write kinds
  are eligible.
- `canonical-atom-v2-learning-refinement.ts` projects the exact existing
  non-Permit, non-admission and non-causal-credit literals into one immutable
  canonical-JSON obstruction profile. Its verdict is
  `BLOCKED_NOT_REFINED_TO_LEAN_LEARN`; it exports no positive refinement,
  Permit, admission or learning capability.
- `canonical-atom-v2-outcome-judgment.ts` represents outcome observation and
  revision-support judgment as separately owned records. Its bundle binds one
  exact schema, proposal, sealed trajectory, observation, criterion, support
  judgment and linear successor shape while retaining explicit
  `NOT_TRUTH_NOT_CAUSAL_CREDIT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING` status.
  It exports no evaluator, adjudicator, owner authenticator or mutation port.
- `canonical-atom-v2-atomic-admission-refinement.ts` projects the separately
  present owner-bound outcome shape and DNRD-5 two-CAS history boundary onto
  the stronger Lean head-bound admission obligations. It preserves their exact
  nonclaim literals and reports five missing composition/Permit/Inv/runtime
  witnesses as `BLOCKED_NOT_REFINED_TO_LEAN_ATOMIC_ADMISSION`; it exports no
  composition, mutation, Permit, validator or learning capability.
- `canonical-atom-v2-verified-admission-gateway.ts` exposes a compatibility v1
  live Lean gate and a separate v2 path. V2 publishes the exact canonical Lean
  request and accepted response, their hashes, Permit envelope and pre/post
  state in one immutable no-replace journal slot; fresh recovery reconstructs
  the predecessor view and revalidates the stored decision without re-running
  the executable. The CLI remains caller-configured and unpinned, nonce/head
  uniqueness is local to the v2 namespace, v2-specific process-crash testing
  is absent, and this is not a complete execution certificate or TS-to-Lean
  source refinement.
- The exact implementation and nonclaims are recorded in the
  [v2 reference-kernel handoff](../../../docs/operations/HSWM_CANONICAL_ATOM_V2_REFERENCE_KERNEL_2026-08-26.md)
  and the
  [content-bound continuation](../../../docs/operations/HSWM_CANONICAL_ATOM_V2_CONTENT_BOUND_RUNTIME_2026-08-26.md),
  followed by the
  [durable-journal continuation](../../../docs/operations/HSWM_CANONICAL_ATOM_V2_DURABLE_JOURNAL_RUNTIME_2026-08-26.md)
  and the
  [typed transition-evidence continuation](../../../docs/operations/HSWM_CANONICAL_ATOM_V2_TRANSITION_EVIDENCE_CONTRACT_2026-08-27.md).
  The current-state boundary is the
  [Permit eligibility contract](../../../docs/operations/HSWM_CANONICAL_ATOM_V2_CURRENT_STATE_PERMIT_ELIGIBILITY_2026-08-27.md),
  followed by the
  [TypeScript-to-Lean refinement obstruction](../../../docs/research/HSWM_TYPESCRIPT_LEAN_REFINEMENT_OBSTRUCTION_2026-08-31.md)
  and the
  [owner-bound outcome judgment boundary](../../../docs/research/HSWM_OWNER_BOUND_OUTCOME_JUDGMENT_BOUNDARY_2026-08-31.md).
  The bounded standard-graph profile and its remaining qualification work are
  recorded in the
  [graph and loop engineering synthesis](../../../docs/research/HSWM_GRAPH_AND_LOOP_ENGINEERING_SYNTHESIS_2026-09-01.md).

The retained historical boundary is also intentionally small:

- `domain.ts` is the deterministic scalar credit state transition.
- `swm0-role-aware-core.ts` is the pure TypeScript numeric T16 center;
  `swm0-role-aware-core-schema.ts` supplies its strict Effect Schema boundary.
  Together they project bounded `H/W/A`, not token-native activation, an LLM
  function cell, training, or causal learning.
- `schema.ts` decodes unknown input and snapshots accepted values.
- `hswm-core-ontology-schema.ts` and `hswm-core-ontology.ts` expose the strict,
  duplicate-aware, pure v1 responsibility-KG contract. They validate a bounded
  ontology projection; they do not create runtime cognition or grant KG writes.
- `runtime.ts` supplies the Effect shell: a capability-service port, typed
  failures, Layers, and one atomic state-plus-journal transaction.
- the existing Python/NumPy SWM experiments remain research/reference oracles;
  they are not silently relabeled as this runtime.

The production/scientific SWM-0W-S2S confirmatory control slice is also
present, but remains pre-dispatch engineering:

- `s2s-confirmatory.ts` contains a hash-pinned pre-preregistration engineering
  candidate for the pilot-adoption binding, integer resource policy, exact seed
  contract, closed monotone phases, seven VOID reasons, and the permanently
  disabled DS-derived compact-competitive phrase. Its resource literals are not
  a scientific freeze; v25 records why timing evidence and chronology remain
  open.
- `s2s-orchestration.ts` defines typed Effect ports for the Python numeric-only
  oracle, verified pulse source, artifact readback, and durable run evidence.
  It performs no beacon, GitHub, or numeric run.
- `s2s-durable.ts` and `s2s-durable-file.ts` implement exact predecessor-linked
  carrier recovery and a private POSIX create-only journal store. This is
  durable local control state, not GitHub observation authority. Byte-equal
  retries must re-establish directory durability before reporting success.
- `s2s-bounded-process.ts` supplies the shell-free, process-group-bounded runner.
  `s2s-live-python.ts` rehashes and invokes an open executable FD, preserves the
  reviewed venv path as `argv0`, owns a private scoped bytecode-cache root, and
  exposes fixed `confirm` and `adjudicate` operations over an exact ten-file
  source closure. `s2s-python-evidence.ts` binds the executor request, runtime,
  source identity, invocation, and exact output bytes without reserializing the
  Python receipt tree. Golden and invalid-input paths are exercised; no valid
  confirmatory candidate has been run.
- `s2s-json.ts` supplies bounded duplicate-aware integer-only JSON decoding.
  `s2s-live-github.ts` implements a read-only, exact-endpoint GitHub observer
  with bounded transport, strict projections, immutable raw-body/download
  snapshots, and request-distinct self-hashed observation receipts. Metadata
  receipts require and bind GitHub's request ID, selected API version, and
  ETag; download receipts separately bind the API redirect and signed-object
  response provenance. `s2s-live-artifact.ts` derives process-local,
  single-module producer/artifact authority, rejects reused request IDs,
  rechecks workflow-attempt identity around lookup and readback, and retains the
  complete receipt objects needed by a later durable envelope. Three
  empty-list observations produce only an explicitly non-probative
  reconciled-absence record.
- The GitHub module also implements lazy standalone run, attempt-one jobs, and
  workflow-runs-for-head revalidation. It snapshots retained bytes once,
  recomputes through the pure constructors, exact-compares nested data, and
  returns only frozen reconstructed observations. The exact head-SHA endpoint
  preserves zero, one, or multiple rows; it does not decide unique-run
  authority. These validators prove internal receipt consistency, not GitHub
  origin. The dormant current-run production graph now fixes the private Live
  observer, but it has not executed while workflow source bytes remain OPEN.
- `s2s-run-authority.ts` now binds authentic registration-B and Live invocation
  capabilities, then defines the exact request-distinct bracket
  `run-start -> jobs -> runs-for-B -> run-end`, immediate byte revalidation,
  unique-roster and fixed-stage/job policy, a self-hashed process-local
  stage-entry capability shape, and a closed Live Layer graph. A root-private
  non-authorizing `Effect<void>` probe verifies the shared acquisition/policy
  path under an injected observer but cannot call the issuer. Production exits
  with `WORKFLOW_SOURCE_BYTES_OPEN` before GitHub configuration or calls, so no
  current-run capability or GitHub-origin observation has been issued.
- `s2s-stage-artifact-permits.ts` derives the fixed stage-read identity from the
  exact current-run bearer, atomically spends finite ordered permits, and carries
  all four bracket receipts into one bounded non-evicting request/receipt
  ledger. `s2s-live-artifact.ts` exposes only lazy zero-identity stage Effects
  and independently rereads the candidate. Successful first-, second-, and
  third-poll lookup now retains the exact initial run, jobs, and every
  artifacts/run pair in one frozen trace capped at eight 1 MiB raw bodies. A
  root-private combined Layer shares one current-run service node with replay
  and fixed reads within one build, while the legacy read-only Layer signature
  remains unchanged. The one-use claim is limited to one trusted process/module
  identity slot; it is not Layer-lifetime or durable replay prevention, and the
  production graph remains dormant while workflow bytes are OPEN.
- `s2s-stage-artifact-read-replay-contract.ts` and
  `s2s-stage-artifact-read-replay.ts` implement the root-private bounded
  structural stage-read replay core. It writes one deterministic stored ZIP
  containing canonical `manifest.json` and the exact concatenated
  `observations.bin`, capped at 12,583,176 bytes, while content-addressing and
  revalidating the already durable predecessor archive instead of duplicating
  up to 64 MiB. The strict unknown-input core returns `Either`; lazy typed
  wrappers use `Effect.suspend`. Source envelopes, claims, archive bytes,
  observation receipts, permits, and candidate FIRST/REREAD ledger continuity
  are independently revalidated. Builders accept only module-issued validated
  reads. File-store recoveries are now process-locally branded, and the selected
  predecessor attachment is copied and read exactly once before producer
  self-validation reuses that inert snapshot.
- `s2s-stage-read-replay-durable-profile.ts` is the root-private local
  create-only bridge for the four reserved success-profile replay slots. It
  exact-binds current-run and predecessor evidence, fully validates every
  carrier and the candidate FIRST/REREAD pair before one non-retried commit,
  then checks the recovered predecessor prefix, latest manifest and claim, and
  replay bytes against the prevalidated snapshots. A non-authorizing fixture
  now exercises one local `REGISTER -> CONFIRM -> ADJUDICATE` chain, byte-equal
  duplicate recovery, fresh-Layer recovery, wrong-predecessor and
  swapped-operation rejection, and lazy hostile-root rejection. This does not
  validate the other profile attachments, implement a closed stage program,
  establish external durability or GitHub origin, or emit production evidence.
- `s2s-preregistration.ts` keeps the validated preregistration and direct-child
  registration-commit lineage runtime-authentic. Commit-B validation now
  returns a module-issued, WeakMap-backed capability with self-hashed immutable
  evidence instead of degrading the verified lineage back to a caller-usable
  SHA string. The current-run acquisition and policy implementation is present,
  but production issuance and dispatch authority remain closed.
- `s2s-live-drand.ts` verifies only a preregistered Quicknet round through the
  pinned local helper. `s2s-live-drand-http.ts` can fetch only that exact
  chain-specific historical/committed URL with one bounded unauthenticated GET;
  it has no `latest`, selection, retry, or fallback path.
- `s2s-zip.ts` validates one exact stored-entry GitHub Actions artifact dialect.
  `s2s-job-sequence.ts` composes isolated registration, candidate, and
  adjudication carriers at event counts `1 -> 6 -> 9`.
- Python-owned `numeric_candidate.json` and `numeric_adjudication.json` remain
  opaque canonical bytes. TypeScript hashes them raw and reads only a strict,
  hash-bound adjudication projection; it never co-authors their receipt tree.
  The candidate phase therefore binds only the raw candidate and confirm-request
  hashes. Its Python receipt is admitted later from adjudication output, after
  the Python replay has validated the candidate's canonical self-receipt.
- the `Ref` control-plane Layer is test-only, intra-process simulation. Three
  GitHub jobs must reconstruct state from immutable predecessor-linked bytes
  and fresh API/download readback; the Layer is not durable truth and does not
  imply exactly-once external effects.
- no composition function appends event 10 or exposes a verdict. That path
  remains closed until the Effect shell directly owns the real Python replay,
  independent GitHub observations, and post-job artifact readback.

This is a `Π` control/evidence boundary around the Python numeric oracle, not a
new learned `W`, an S2S efficacy result, or authorization to dispatch the
future-seeded gate. Raw transition, store, adapter, and generic-submit
capabilities are intentionally absent from the package root export until a
production orchestrator owns all provenance checks end to end.

Independent exact-byte reviews drove repairs across the source-A/B, pulse,
resource-accounting, artifact-size, journal, process, ZIP, and structural
carrier boundaries, with regression coverage on the resulting bytes. The slice
remains `BLOCKED_PRE_PREREG`: the bounded adapters and closed current-run Layer
graph are present, but no issued current-run/dispatch authority, workflow,
complete replay-closed durable evidence deployment, or external event-10
finalizer exists. The immutable v21 checkpoint is recorded in the repository
[`historical assertion-shell implementation handoff`](../../../docs/operations/HSWM_SWM0W_S2S_ASSERTION_SHELL_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and its
[`v21 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v21.json).

The historical v22 design entrypoint is the
[`v22 Occam-core/process-topology decision`](../../../docs/operations/HSWM_SWM0_OCCAM_CORE_AND_S2S_PROCESS_TOPOLOGY_DECISION_NEXT_SESSION_2026-08-23.md)
and its
[`v22 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v22.json).
It selects a background Effect root plus authenticated one-shot IPC for the
future evidence workflow but leaves both production gates closed. The immediate
implementation target is instead a pure TypeScript T16 capsule that joins
explicit role-bearing incidences, learned recipient-conditioned transport, and
one-sweep activation, with Effect at the strict decode/composition boundary and
independent Python parity. No runtime code or scientific result changed in v22.

The historical v23 implementation entrypoint is the
[`v23 role-aware TypeScript core implementation`](../../../docs/operations/HSWM_SWM0_ROLE_AWARE_TYPESCRIPT_CORE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and its
[`v23 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v23.json).
At commit `a9aff88`, the internal `swm0-role-aware-core` modules implement the
fixed pure TypeScript T16 one-sweep equation behind strict Effect
Schema/Either/tagged-error boundaries. Exact role/member addresses, all 870
little-endian float64 parameter bytes, six recipient outputs, Q
removal/private-snapshot restoration, member actions, registered role
perturbations, and broadcast are independently pinned to two officially parsed
Python learned archives. The capsule is intentionally absent from `src/index.ts`.
Before any root export, review source-provenance/version migration and explicit
composition with the existing scalar credit runtime. No TypeScript training,
LLM function cell, causal update, topology learning, target-scored damage,
production occurrence, or scientific verdict is claimed.

The historical v24 continuation entrypoint is the
[`v24 test-only hosted process-continuity implementation`](../../../docs/operations/HSWM_SWM0W_S2S_TEST_ONLY_HOSTED_PROCESS_CONTINUITY_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and its
[`v24 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v24.json).
Commits `9063716` and `e729ef2` implement a dispatch-only, package-internal
Effect root with authenticated one-shot IPC and the exact hosted
background/wait/cancel workflow. GitHub run `32654010771` observed both jobs as
individual successes, including REGISTER and ADJUDICATE uploads, the expected
CONFIRM no-files failure, injected-unknown no-retry diagnostics, and explicit
READY cancellation. This closes only the test-only hosted mechanics gate.
`H/W/A/F`, scalar/T16 composition, package-root exports, production authority,
shared durability, exactly-once behavior, preregistration, Q/B/R, and every
scientific claim remain unchanged or open.

The current continuation entrypoint is the
[`v25 pre-freeze resource-policy review decision`](../../../docs/operations/HSWM_SWM0W_S2S_PRE_FREEZE_RESOURCE_POLICY_REVIEW_DECISION_NEXT_SESSION_2026-08-23.md)
and its
[`v25 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v25.json).
The exact `75/245/75` candidate remains a valid package-internal arithmetic
fixture but is rejected for production/preregistration freeze. One successful
three-draw pilot does not supply the required workflow p95 or a production-
equivalent 20-task profile; REGISTER's 75-minute candidate also conflicts with
the existing 65-minute maximum pulse lead. No policy literal, workflow,
protocol config, preregistration, future randomness, or runtime implementation
changed. Resume at the chronology-and-timing protocol design gate before any
heavy resource-profile dispatch.

One deeply frozen, root-private `S2S_STAGE_ARTIFACT_SPECS` value now owns the
fixed REGISTER, CONFIRM, and ADJUDICATE artifact mappings used by live
predecessor reads and replay source references. Stage-specific literals remain
correlated in TypeScript. The production-intended upload-postcondition
representation and byte-budget skeleton also separates its exact
12,583,176-byte carrier ceiling from the 16 MiB profile slot. At code checkpoint
`1f45f4b`, the root-private postcondition core adds exact correlated Effect
schemas, a canonical 37-key self-receipted manifest, deterministic two-member
stored-ZIP build/validation, retained raw-observation reconstruction, and
download/archive/prepared-member cross-binding. Builders accept only
`TEST_ONLY_NON_AUTHORIZING` permit evidence; structural recovery remains
explicitly non-authorizing even when it rechecks a serialized trusted scope.
The 19 focused tests and 310 full package tests close only this strict
codec/reconstruction falsification gate.

At code checkpoint `36b4c9b`, `s2s-prepared-stage-carrier.ts` adds disjoint
module-authentic production and test registries, internal stage/role/job/member
derivation, exact predecessor replay binding, idempotent same-byte preparation,
conflict rejection, and one anti-replenishing production semantic slot.
`s2s-stage-upload-assertion.ts` adds the fixed 1/2/3-attempt ledger topology,
atomic `Ref.modify` reservation, and `Effect.acquireUseRelease` burn semantics.
`s2s-stage-upload-outcome.ts` admits only the seven frozen v16 outcomes and
never authorizes retry or external exactly-once claims. The positive probe and
all generic append/use/seal mechanics are explicitly test-only; production
paths fail with `PRODUCTION_ASSERTION_SHELL_OPEN`. The 33 new focused tests and
343 full package tests close only this process-local mechanics gate.

The reviewed ownership and gate order remain in the immutable
[`v16 stage-upload assertion design handoff`](../../../docs/operations/HSWM_SWM0W_S2S_STAGE_UPLOAD_ASSERTION_DESIGN_NEXT_SESSION_2026-08-23.md)
and
[`v16 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v16.json).
The prior root-private golden vertical composition remains test-only as recorded
by the
[`v15 implementation handoff`](../../../docs/operations/HSWM_SWM0W_S2S_GOLDEN_VERTICAL_COMPOSITION_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and
[`v15 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v15.json).
Local receipts still cannot satisfy production confirmatory events or
`S2SArtifactEvidence` inputs.

Earlier immutable checkpoints remain indexed by the
[`v14 golden design handoff`](../../../docs/operations/HSWM_SWM0W_S2S_GOLDEN_VERTICAL_COMPOSITION_DESIGN_NEXT_SESSION_2026-08-23.md)
and
[`v14 KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v14.json),
the
[`v13 durable replay-profile handoff`](../../../docs/operations/HSWM_SWM0W_S2S_DURABLE_REPLAY_PROFILE_INTEGRATED_NEXT_SESSION_2026-08-23.md)
and
[`v13 KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v13.json),
and the
[`v12 stage-read replay-core handoff`](../../../docs/operations/HSWM_SWM0W_S2S_STAGE_READ_REPLAY_CORE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and
[`v12 KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json).

At code checkpoint `0fe7791`, the root-private selector-free Effect assertion
service and replay snapshot are implemented. One scoped Layer claim owns one
exact `Effect.acquireUseRelease` lease; the shell derives the 1/2/3-attempt
selectors internally, revalidates raw GitHub-shaped observations and strict
stored ZIP/member bytes, builds the structural postcondition, and issues only
module-authenticated opaque completion/replay values. The remaining
archive-receipt `Date.now()` path now uses the Effect Clock. All 364 package
tests pass, including the inherited hostile matrix under the disjoint
`TEST_ONLY_NON_AUTHORIZING` Layer.

The production root remains deliberately fail-closed and has not executed.
There is still no genuine issued production bearer, filled
upload-postcondition profile occurrence, complete-stage durable
commit/recovery, reviewed workflow
authority, GitHub-origin evidence, external shared durability,
independent-process recovery, preregistration, future randomness, dispatch,
event 10, or scientific verdict. This checkpoint changes only `Pi`; `H`, `W`,
`A`, and `F` remain unchanged, and the outcome-bound causal-learning loop did
not advance. V24 now observes the selected topology only in a disjoint
test-only hosted probe. A production process-continuity decision, bounded
external shared-POSIX proof, complete-stage program, and independent recovery
remain required before the production root can advance.

The v20 read-only architecture audit freezes a prerequisite for workflow
wiring: process-local object/`WeakMap` bearers do not cross ordinary GitHub
Actions step processes. The reviewed workflow must either retain one trusted
long-lived Effect root or define independently authenticated deterministic
reacquisition; serialized capabilities and trusted evidence remain data, not
authority. The production shell owns the real observer internally, uses one
Effect Clock for sleeps and timeouts, issues completion only after strict
postcondition revalidation, and remains fail-closed until workflow bytes and
process continuity are resolved. Its immutable contract remains in the
[`v20 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v20.json)
and
[`v20 architecture-audit handoff`](../../../docs/operations/HSWM_SWM0W_S2S_ASSERTION_SHELL_ARCHITECTURE_AUDIT_NEXT_SESSION_2026-08-23.md).

The v21 implementation retains that prerequisite exactly. The production
preflight checks workflow source and then the separate process-continuity gate
before config, authority, capability, claim, observer, transport, or I/O.
Neither gate is bypassed by the test Layer, and serialized values never restore
authority. V22 later selected a topology and v24 observed its disjoint test-only
mechanics; neither checkpoint authorizes production workflow wiring.

The earlier
[`v11 lookup-trace/shared-Layer handoff`](../../../docs/operations/HSWM_SWM0W_S2S_LOOKUP_TRACE_SHARED_LAYER_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and
[`v11 local KG projection`](../../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json)
also remain immutable historical checkpoints.

The in-memory Layer's static capability-ID allowlist is configuration for tests
and local scaffolding, not identity authentication. This slice is not evidence
of learned set-to-set `W`, durable causal learning, or a complete HSWM. A
production store, capability verifier, and outcome/provenance verifier are still
required before durable use.

Run the exact local verification surface with:

```sh
npm ci --ignore-scripts --no-audit --no-fund
npm run verify
```
