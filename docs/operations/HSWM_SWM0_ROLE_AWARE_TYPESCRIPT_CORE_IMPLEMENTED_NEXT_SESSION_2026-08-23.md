# HSWM SWM-0 role-aware TypeScript core implemented — next-session handoff

Date: 2026-08-23
Workspace parent: `1a8a1db806bac3f36cd88b566bf14bd90604ce1e`
Implementation commit: `a9aff88d37f5d0adaaf97c11fbfec643aa36eac0`
Continuation KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v23.json`
Predecessor KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v22.json`
Status: `BOUNDED H/W/A ENGINEERING PROJECTION IMPLEMENTED / PACKAGE-ROOT PUBLICATION DEFERRED / SCIENTIFICALLY UNJUDGED`

## Resume capsule

The v22 Occam-core target is implemented and pushed on `main`. A strict
TypeScript 5.9.3 / Effect 3.22.1 capsule now joins explicit role-bearing
incidence `H`, a recipient-conditioned T16 parameter operator `W`, and one
simultaneous recipient activation sweep `A`. The numeric center is pure
TypeScript. Effect Schema, Either, and a tagged error algebra own its bounded
input/archive/intervention shell.

This is the first falsifiable TypeScript engineering projection of that
`H/W/A` conjunction. It is not the complete HSWM loop. The source archives were
produced by the existing Python learned-model path; TypeScript verifies their
strict projected bytes and hashes but does not authenticate provenance, replay
training, train a model, score an efficacy target, execute an LLM function
cell, attribute an external outcome, or issue `delta-W/delta-H`.

The package root deliberately does not export this first capsule. Its internal
source modules are available for reviewed in-package composition, while public
publication waits for an explicit source-provenance/migration adapter and a
decision about how operator-valued `W` composes with the existing scalar
outcome-credit runtime. Do not silently reinterpret the scalar
`SemanticWeight` as this operator.

The future S2S evidence branch remains where v22 left it: a background
long-lived Effect root plus authenticated one-shot IPC is selected in design,
but timing, hosted survival, IPC, shared durability, workflow source, and both
production preflight gates remain open. Do not author the production workflow
from this checkpoint.

Use the complete `effect-ts-functional` skill again before changing this core
or its package surface. Keep TypeScript `5.9.3`, Effect `3.22.1`, Node
`24.13.0`, and Vitest `3.2.7` pinned unless a separate migration is reviewed.

## Canonical role, evidence, and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
`docs/canon/HSWM_CONSTITUTION_2026-08-20.md`. Its evolving hypergraph is one
living harness, world model, and continuous learner. TypeScript, Effect,
Python, the repository KG, workflows, and MCPs are bounded projections and
interfaces rather than separate cognition, routing, or learning systems.

### Target identity

```text
role-bearing n-ary H
  -> learned recipient-conditioned semantic transport W
  -> bounded activation A
  -> typed LLM function cell F
  -> attributable external outcome
  -> causal credit
  -> versioned bounded delta-W/delta-H under Pi
```

### Evidence now checked in

- `H`: one bounded hyperedge with fixed semantic roles `r0/r1/r2`, two
  explicitly addressed member slots per role, distinct incidence/node IDs, and
  finite four-channel presweep activations. Caller enumeration order has no
  semantic force.
- `W`: one fixed T16 recipient-conditioned operator with the exact six tensor
  shapes and all 870 float64 parameters committed as canonical little-endian
  bytes. It is a strict projection of a Python learned archive, not a
  TypeScript learning claim.
- `A`: one simultaneous pure TypeScript sweep returns two channels for each of
  the six exact physical recipients. The explicit ascending loop order matches
  the independent Python scalar oracle byte for byte.
- `F`: unchanged. The numeric T16 equation is not an LLM-executed typed
  semantic function cell and establishes no function-cell efficacy.
- `Pi`: the local capsule advances bounded decoding, typed failure, resource
  limits, opaque authentic handles, exact commitments, and safe intervention
  restoration. It does not advance production workflow authority.
- outcome-bound causal-learning loop: unchanged. No outcome attribution,
  eligibility, credit, optimizer, recurrence, durable update, or topology
  rewrite exists in this capsule.

### Conceptual delta from v22

V22 recorded a missing reusable TypeScript `H/W/A` conjunction. V23 implements
that bounded engineering conjunction for one fixed T16 gate. It does not close
the conceptual delta to HSWM's full target identity: `F`, external outcome,
causal credit, accepted state transition, topology plasticity, and the changed
next activation caused by learning remain absent.

Tests below are evidence instruments for this narrow claim. Their success is
not HSWM progress beyond the implemented semantics.

## Implemented files and contract

```text
src/hswm/effect-runtime/src/swm0-role-aware-core-schema.ts
src/hswm/effect-runtime/src/swm0-role-aware-core.ts
src/hswm/effect-runtime/test/swm0-role-aware-core.test.ts
src/hswm/effect-runtime/test/public-api.test.ts
_research/swm0_role_aware_core/generate_parity_fixture.py
tests/fixtures/swm0_role_aware_core_python_v1.canonical.json
tests/test_hswm_swm0_role_aware_core_fixture.py
```

The fixed engineering scope is:

| Property | Exact value |
|---|---:|
| hyperedges | 1 |
| roles | 3 (`r0`, `r1`, `r2`) |
| members per role | 2 |
| input channels per incidence | 4 |
| output channels per recipient | 2 |
| sweeps | 1 |
| hidden width | 16 |
| parameters | 870 |
| parameter bytes | 6,960 |

The exact tensor roster is `phi_w(3,4,16)`, `psi_w(3,4,16)`,
`unary_w(3,2,16)`, `pair_w(3,3,2,16)`, `q_w(3,2,16)`, and
`out_b(3,2)`.

The boundary rejects excess fields, proxies, accessors, symbols, sparse
arrays, non-finite values, malformed topology, wrong tensor rosters/shapes,
wrong byte or aggregate commitments, noncanonical encodings, and unbounded
string/key surfaces before hashing or decoding. Fixed tensor and Q base64
lengths are exact; the surface also has a 4,096-character per-value/key-safe
ceiling and a 16,384-character cumulative string/key budget.

Public operator and result values are frozen opaque handles. Module-private
WeakMap snapshots own copied numeric state. Q removal replaces the exact 768 Q
bytes with positive-zero bytes. Restoration requires the module-private
original Q snapshot and the original parameter/core/operator commitments; a
caller cannot authorize an unintervened zero-Q operator by recomputing a
self-consistent receipt. Cross-model replay, missing/excess fields,
invalid/oversized encodings, proxies, and accessors fail closed.

Within-role member swaps preserve physical-recipient equivariance. The two
registered role cycles produce non-identical outputs and match the Python
oracle, so they are demonstrated as non-invariant perturbations only. The
fixture contains no targets or R2 scoring; the scientific target-scored role
damage gate remains open.

Within-role broadcast uses an already issued baseline result, performs zero
additional operator sweeps, and emits a separately typed frozen control result.
No recurrence or update API exists.

## Independent parity evidence

The canonical fixture contains two deterministic, real one-update Python
learned T16 archives and six worlds per model. For each model it records all
eight `S2^3` member controls, both registered role cycles, Q removal/restoration,
and within-role broadcast.

```text
fixture byte length: 172400
fixture raw SHA-256: 65234fd31745dec2f8f616b01bef329a40044d064448e169d87ebcfb361f4ef6
fixture receipt:     8c437d71ff8af403e546729eb24707ef8b331b2c9520f48df20ae8822b0d3d7b
model A parameters:  02169d99cf2f376105851245dd99f30b627eba7d89a7e3f87e556284ede71c4b
model B parameters:  94548fc587c16d29764292857daa4960b5a75d6dec42ce09b2d5bcabe20aead1
```

The checked-in Python test passes each embedded learned archive through the
authoritative `parse_learned_model_archive` path, reconstructs its exact
parameters, and independently recomputes scalar/NumPy comparison metadata.
The generator `--check` refits and regenerates the complete fixture without
changing its checked-in bytes.

The explicit Python scalar equation is the exact-order byte oracle. General
NumPy einsum is a separate implementation and is compared with fixed absolute
and relative tolerance `5e-14`; it is not the source of byte equality.

## Verification at implementation commit

- `npm run verify`: TypeScript check PASS; 30 Vitest files and 379 tests PASS;
  build PASS; package dry-run PASS.
- focused TypeScript core: 14/14 PASS, including all 720 incidence enumeration
  orders and the coherent forged-Q-receipt regression.
- Python operator/training/protocol/fixture regression: 84/84 PASS.
- Python fixture contract alone: 2/2 PASS.
- bounded Proxmox scratch regeneration: `MATCH`, with the exact fixture hash
  and receipt above; successful scratch cleaned automatically.
- independent read-only core review: no unresolved blocker.
- `git diff --check`: PASS.
- protected unrelated paths remained uncommitted.

This is routine engineering evidence. It creates no material scientific result
and requires no `F1_R8_RESULTS_LOG.md` entry or content-addressed research-result
receipt.

## Public-surface and composition decision

The new modules are intentionally absent from `src/index.ts`, and
`public-api.test.ts` freezes that absence. Before exporting them, review:

1. a strict source-provenance and archive-version migration adapter;
2. the relationship between existing scalar outcome-credit
   `SemanticWeight` and operator-valued T16 `W` without replacing one by name;
3. ownership of operator state transitions, rollback, and durable lineage;
4. whether the fixed `r0/r1/r2` T16 projection stays an experimental internal
   type or becomes one versioned public specialization; and
5. which Effect service/Layer composition is actually required around the pure
   core rather than adding an orchestration duplicate.

Do not add a TypeScript optimizer merely to make the port look complete. A
future learning slice must bind an attributable outcome to a falsifiable state
transition and demonstrate that the accepted transition causes changed future
activation while retention/removal controls remain intact.

## Gates that remain open

- source-provenance authentication and public migration compatibility;
- composition with the scalar credit runtime;
- TypeScript training, outcome credit, recurrence, durable `delta-W/delta-H`,
  rollback, and learned topology;
- LLM-executed typed function cells;
- target-scored role-cycle damage/R2 and every scientific S2S verdict;
- production background root, authenticated IPC, hosted-runner survival,
  corrected job-time inequalities, shared external POSIX durability, complete
  stage commit/recovery, and workflow-source freeze;
- GitHub origin, preregistration, future randomness, dispatch, event 10,
  scientific adjudication, SWM-1, and complete HSWM.

## Next-session order

1. Read the constitution, Occam core, S2S gate, v22 and this v23 handoff/KG,
   and the complete `effect-ts-functional` skill.
2. Preserve the two unrelated dirty continual-live paths below.
3. Audit the internal T16 package boundary and design the smallest explicit
   composition with the existing scalar credit runtime; do not conflate scalar
   credit with operator-valued semantic transport.
4. Freeze source-provenance/archive-version migration semantics before any
   package-root export, then add the export only in a separate reviewed gate if
   it is justified.
5. Specify the first outcome-bound state-transition experiment only after the
   composition semantics are falsifiable. Keep TypeScript training, recurrence,
   topology learning, and scientific claims downstream of their own evidence.
6. Keep both production workflow gates closed. Later return to the evidence
   branch at timeout repair and a test-only hosted background-root/IPC
   feasibility workflow, followed by shared-POSIX and complete-stage recovery.
7. Do not create preregistration, dispatch, event 10, or a scientific verdict
   from this engineering checkpoint.

## Protected unrelated worktree paths

```text
src/hswm/experiments/continual_live.py
tests/test_hswm_continual_live.py
```

These changes predate this checkpoint. They were not staged, committed,
rewritten, or used as evidence.

## Exact nonclaims

No public TypeScript T16 API, TypeScript training event, source-provenance
authentication, scalar-credit composition, optimizer, recurrence, LLM
function cell, attributable external outcome, causal update, durable state
transition, topology mutation, target-scored role damage, scientific S2S PASS,
production process root, authenticated IPC, hosted feasibility run, production
workflow/upload, shared durable root, complete-stage recovery, GitHub origin,
preregistration, dispatch, event 10, scientific verdict, or complete HSWM was
produced. The repository KG is a bounded continuation projection, not HSWM
cognition. Remote KG publication was `NOT_ATTEMPTED`.
