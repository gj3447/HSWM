# HSWM Effect runtime functional boundary

> **Status:** `EFFECT_BOUNDARY_LINT_ENFORCED / SEVEN_LANES_EXEMPT /
> TS_MIGRATION_GATES_NOT_CLOSED / DECISIVE_LOOP_NOT_IN_TYPESCRIPT /
> G0_NOT_PASSED / G1_LOCKED`
>
> **Date:** 2026-09-06
>
> **Audit it answers:** the 2026-09-05 TypeScript/Effect completeness audit
> (15 agents, skeptic re-verified) at commit `4dcba752`.
>
> **KG projection:** [`HSWM_EFFECT_RUNTIME_FP_BOUNDARY_ONTOLOGY.v1.json`](../../ontology/identity/hswm_core/HSWM_EFFECT_RUNTIME_FP_BOUNDARY_ONTOLOGY.v1.json)

## 1. Answer

The TypeScript/Effect runtime is now functional in shape as well as in
substance, outside seven named lanes that still carry imperative code for a
stated reason.  Concretely:

- there are exactly two Node adapters, `effect-posix-filesystem.ts`
  (`PosixFileSystem`) and `effect-bounded-subprocess.ts`
  (`BoundedSubprocess`); every refactored store, journal, control journal and
  CLI takes the service value or requires the `Context.Tag`;
- there is one process boundary, `effect-process-main.ts`
  (`runProcessMain` for stdin-JSON executables, `runArgvProcessMain` for
  flag-driven CLIs), and it is the only place outside executable guards where
  `Effect.run*` is called;
- refusals and failures are values (`ProcessRefusal`, `Data.TaggedError`
  classes, `Either.left`); no `throw` remains outside the lanes;
- module-level mutable state is gone: brands and internal seams are private
  class fields, the verified-admission root semaphores live in a
  `ProtectedRootLocks` service, and constant sets are typed `ReadonlySet`;
- the local Permit commit store is a service (`LocalPermitCommitStoreService`
  with `makeLocalPermitCommitStoreLayer`), not only a factory;
- a dependency-free lint, `scripts/lint-effect-boundary.mjs`, enforces all of
  this in `npm run check` and therefore in CI, with a shrinking-only lane
  allowlist whose stale entries fail the run.

None of this moves the decisive HSWM loop into TypeScript.  The six migration
gates of
[`HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md`](../research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md)
keep the dispositions the audit gave them, and every judgment step of the
sealed-trajectory → outcome → credit → canonical-revision → held-out-behavior
loop stays in Python.  This document and its projection record code shape,
not scientific status.

## 2. Target identity, current evidence, and conceptual delta

| Layer | Statement |
|---|---|
| Target identity | HSWM remains one token-native LLM-function macro-neural network whose evolving canonical hypergraph is living harness, world model, and continuous learner under typed outcome-bound dynamics. |
| Current evidence | The runtime is a journal/Permit/projection substrate with synthetic fixtures only; the G1 opaque v3 instrument is preregistered in draft and unrun; G0 is not passed. |
| Conceptual delta | None at the research level.  The delta is engineering: the substrate's I/O, refusal, and state conventions are now enforced by a lint rather than by convention, so a future TypeScript function-cell (gate 4) has one adapter shape and one process boundary to build on. |

## 3. Migration gates (unchanged by this work)

| Gate | Claim assessed | Disposition | Code evidence |
|---|---|---|---|
| MG-1 Contract | Schemas frozen with migration/version semantics | UNDERDETERMINED | Schema ingress everywhere; `state-journal.ts:535` "migration is not implemented"; `domain.ts` `MIGRATION_UNSUPPORTED` |
| MG-2 Oracle parity | Python numeric reference behind a typed adapter with exact parity | UNDERDETERMINED | T16 parity at 5e-14, but all results `TEST_ONLY_NON_AUTHORIZING`, `typescriptTrainingClaimed: false` |
| MG-3 Durability | Atomic persistent CommitStore, crash recovery, replay | UNDERDETERMINED | O_EXCL+fsync+no-replace link, SIGKILL crash tests, one-winner CAS; anti-rollback is a nonclaim; HSWM-core `CommitStore` is an in-memory `Ref` |
| MG-4 Function-cell | Scoped LLM/tool cell execution | RED | 0 LLM calls in the TypeScript sources; `F` is an id registry |
| MG-5 Learning | Verified outcomes and credit bound to ΔW/ΔH | RED | `learning-refinement.ts` emits only `BLOCKED_NOT_REFINED_TO_LEAN_LEARN` |
| MG-6 Authority | TypeScript as source of truth after parity/replay | RED | Temporal runs simulation only; completion authority is Python; PS-3 unproved |
| LOOP-TS | TypeScript executes the decisive loop | RED | TypeScript is called once per credited admission over stdin/stdout to verify a transition Python already decided |

## 4. Shortfalls named by the audit and what closed them

| Gap | Before (2026-09-05) | After (2026-09-06) | Status |
|---|---|---|---|
| FP-GAP-1 imperative I/O adapters | async/await Node code lifted at the edge by `Effect.tryPromise` (60 sites); no `@effect/platform` | `PosixFileSystem` + `BoundedSubprocess` services; refactored files take the service value | closed outside lanes |
| FP-GAP-2 throw as refusal | 602 statement throws in the baseline tree (corrected count) | Effect programs behind `runProcessMain` / `runArgvProcessMain`; `ProcessRefusal`, tagged errors, `Either.left` | closed outside lanes |
| FP-GAP-3 runtime started inside a library | `content-file.ts:275,316` `get(...).pipe(Effect.runPromise)` | `yield* get(...)`; `Effect.run*` confined to the boundary and executable guards | closed |
| FP-GAP-4 module-level mutable state | 21 module-level Map/Set/WeakMap/WeakSet, 3 module-level `let`, WeakSet brand in the G0 kernel | private fields (`#issued`, `#commit`, `#compiledBytes`, `#snapshot`), `ProtectedRootLocks` service, `ReadonlySet` constants | closed outside lanes |
| FP-GAP-5 plain factory, no service | `makeLocalPermitCommitStore` returned a frozen object | `LocalPermitCommitStoreService` tag + `makeLocalPermitCommitStoreLayer(rootPath, verifier, clock)` requiring `PosixFileSystem` | closed |
| FP-GAP-6 no lint | conventions and the compiler only | `lint-effect-boundary.mjs` R1–R5 in `npm run check` and CI | closed |

`@effect/platform` was evaluated and rejected: it cannot express `O_NOFOLLOW`
reads, directory fsync, no-replace hard links, or detached process groups,
and it would add an unpinned dependency family against the exact-pin policy.

## 5. Packages (one commit each, in merge order)

| Package | Commit | Files | Verification |
|---|---|---|---|
| P-0 foundation services + local Permit commit | `d9e5c1a` | `effect-posix-services.ts`, `effect-process-main.ts`, `canonical-atom-v2-local-permit-commit*.ts` | 18 Permit tests, 3 process tests, 3 Python bridge tests |
| lint baseline | `75fdf15` | `scripts/lint-effect-boundary.mjs`, allowlist | report only at that commit |
| P-1 content file store | `ab211af` | `canonical-atom-v2-content-file.ts` | content-file 3, content-runtime 8, durable-runtime 29, durable-rdf 5 |
| P-1b adapter split | `edee9d3` | `effect-posix-filesystem.ts`, `effect-bounded-subprocess.ts`, umbrella | `dnrd5-source-closure` green again (child_process left the closure) |
| P-3 module-level state | `68513d9` | G0 kernel, Temporal domain, durable runtime, durable RDF projection, SWM0 core, verified-admission gateway | 91 tests incl. pinned T16 hashes and both tsconfigs |
| P-5 graph-loop journal + pure cores | `8ee390b` | `graph-loop-engineering.ts`, `content.ts`, `hypergraph-projection.ts`, `current-state-permit.ts` | 66 tests + repo-level effect-runtime suite |
| P-5b receipt digest | `1d44bc6` | `hypergraph-projection-receipt.ts` | receipt + projection tests |
| P-2 subprocess runner + CLIs | `dad5d21` | `graph-loop-research-job.ts`, `graph-loop-job-process.ts`, `hypergraph-projection-process.ts`, `effect-process-main.ts` | 41 tests; CLI usage/exit-code parity smoke |
| P-7 rehearsal fixtures | `fdc4c9d` | both rehearsal modules, CLI, repo-level tests | 28 tests |
| P-4 state journal file | `e00bd0f` | `canonical-atom-v2-state-journal-file.ts` | 86 tests incl. 14 interruption checkpoints and the I/O fault plan |
| P-6 DNRD routing-diagnostic process | `547b02f` | `canonical-atom-v2-routing-diagnostic-process.ts`, `_research/dnrd/execute.py` core source list | 40 vitest (incl. the fresh-child-process test over the dist build), 61 `tests/test_hswm_dnrd_execute.py`, `npm run build:dnrd` |
| P-8 lint enforcement | `1feb30c` | `package.json` `check`, allowlist, lint report | `npm run check` green; 0 violations outside lanes |

### 5.1 P-6 contract notes

P-6 rewrites the DNRD-5 routing-diagnostic process root as one Effect program
with the stdin/stdout/stderr/exit contract that
`_research/dnrd/execute.py` and `tests/test_hswm_dnrd_execute.py` consume.
The hand-rolled wire decoders were kept (as `Either` programs) because the
tests and the Python bridge pin their exact refusal strings; the durable mount
adapter is provided per use as a Layer; the only observable delta is that a
genuine defect now exits 3 with a `defect:` line instead of 2.  Because the
process now imports the foundation modules, the DNRD core source list in
`_research/dnrd/execute.py` grew by the four foundation files; historical
checked-in manifests are untouched.

## 6. Lint rules and exemption lanes

| Rule | Forbids |
|---|---|
| R1 | module-level `let` |
| R2 | `Effect.run*` outside `effect-process-main.ts` and the `import.meta.url` guard of `*-process.ts` / `*-cli.ts` |
| R3 | statement-position `throw` |
| R4 | module-level `const x = new (Weak)?(Map|Set)` unless typed `ReadonlyMap` / `ReadonlySet` |
| R5 | `async` functions |

| Lane | Why it keeps imperative code |
|---|---|
| HISTORICAL_S2S | SWM-0W S2S lane retained byte-stable for the ignored handoff tests and sealed hosted-process receipts; not migrated before the G1 verdict (SR-4/SR-5) |
| DNRD5_PROTOCOL | `canonical-atom-v2-dnrd5-*.ts` are read by the source-closure judge and pinned by the DNRD-4/DNRD-5 worktrees; converted only under a DNRD amendment |
| TEMPORAL_SDK_LANE | Temporal workflow/worker/activities compiled under `tsconfig.temporal.json`; the workflow sandbox forbids Effect |
| GRAPH_STANDARDS_PINNED | `canonical-atom-v2-jsonld-view.ts` is byte-bound by the graph-standards acceptance lock |
| FOUNDATION_ADAPTER | the POSIX filesystem adapter's async/throw sit inside `Effect.tryPromise` / `acquireUseRelease` callbacks mapped to `PosixIoError` |
| NEO4J_DRIVER_ADAPTER | `neo4j-driver` transaction functions are Promise-based and roll back only by throwing |
| PURE_KERNEL_INVARIANT_GUARD | two index guards in the pure T16 kernel are invariant defects under `noUncheckedIndexedAccess`; the pinned T16 hashes would expose drift |

The allowlist is `src/hswm/effect-runtime/scripts/effect-boundary-allowlist.json`;
the report the projection binds is
`src/hswm/effect-runtime/scripts/effect-boundary-lint-report.json`, regenerated by

```bash
cd src/hswm/effect-runtime
node scripts/lint-effect-boundary.mjs --json > scripts/effect-boundary-lint-report.json
```

Known residue that the lint cannot see and this document names instead:
`projectionGraphSha256` (an `Either.getOrThrowWith` wrapper kept only for the
neo4j adapter lane), the `beforeSlotLink` test seam of the state journal
(`() => Promise<void>`, consumed by one `Effect.tryPromise`), and
`driver.close()` inside the hypergraph projection CLI's release step.

## 7. Verification

```bash
cd src/hswm/effect-runtime
npm run check            # tsc (both tsconfigs) + Effect boundary lint
npm run lint:boundary -- --all
npx vitest run           # full package suite
npx vitest run ../../../tests/effect-runtime
cd ../../..
uv run --locked --extra dev pytest -q \
  tests/test_hswm_atom_v2_permit_bridge.py \
  tests/test_hswm_g1_opaque_v3.py \
  tests/test_hswm_effect_fp_boundary.py \
  tests/test_kg_bundle_graph_view.py
uv run --locked --extra dev python scripts/build_hswm_effect_fp_boundary_ontology.py --check
uv run --locked --extra dev python scripts/upsert_hswm_effect_fp_boundary.py
```

## 8. Governance notes

- **Burden cap (D-4, RATIFIED).** These commits touch core paths only where
  they touch `canonical-atom-v2-local-permit-commit*`; the rest count against
  the ≥50% core share of the 100-commit window that opened at `4dcba752`.
  `scripts/check_hswm_closure_burden_cap.py` reports the running share; the
  window is open and below share as of this document, and the ratified
  disposition on violation is one `INSTRUMENT_RED` row in `F1_R8`, not scope
  expansion.
- **SR-4 (PROPOSED).** The KG projection is a new ontology JSON version
  created before the G1 verdict on the user's explicit 2026-09-06 instruction
  to connect this work to the KG; the deviation is recorded as a node in the
  projection rather than hidden.
- **SR-5 (PROPOSED).** The projection binds counts and digests, not exact
  bytes of live source files; only the lint report, allowlist, lint script,
  this document, and the gate document are hash-bound.

## 9. Evidence status

Engineering only.  No evidence receipt is added and `F1_R8_RESULTS_LOG.md` is
unchanged.  The fractal status remains
`SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`; G0 is not passed and
G1 is locked.
