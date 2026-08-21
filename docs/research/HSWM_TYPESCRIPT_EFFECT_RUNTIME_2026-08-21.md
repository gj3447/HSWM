# HSWM TypeScript + Effect runtime boundary

Date: 2026-08-21
Authority: `USER_PRIMARY` for the TypeScript/Effect direction; architecture
details below are `SECONDARY_AI_PROPOSED`.
Current evidence status: `ENGINEERING_SCAFFOLD / SCIENTIFIC_UNJUDGED`.

The exact user source is preserved at
[`USER_PRIMARY_HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.txt`](../canon/sources/USER_PRIMARY_HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.txt).

## Decision

HSWM's long-lived production runtime should be TypeScript-first and use Effect
for typed services, failures, resources, concurrency, and composition. The
existing Python/NumPy finite-world and learning experiments remain the numerical
reference and evidence oracle until a TypeScript implementation independently
matches their frozen contracts. This is a staged boundary, not a big-bang
rewrite and not a relabeling of Python experiments as a production runtime.

The initial package is
[`src/hswm/effect-runtime/`](../../src/hswm/effect-runtime/). It pins
Effect `3.22.1`; it does not mix Effect v3 and v4 APIs.
The package is private and versioned `0.0.0` while the boundary is still being
formed.

## Why Effect belongs at this boundary

Effect is most valuable where HSWM must make `Π` operational:

- unknown input is decoded before it becomes a domain value;
- expected failures remain typed values instead of thrown control flow;
- capability verification, durable storage, function-cell execution, and the
  Python oracle become explicit services;
- Layers form one visible composition graph;
- resources, cancellation, retry schedules, and bounded concurrency can be
  defined at the shell rather than leaking into semantic mathematics;
- tests replace live services with deterministic Layers.

Effect is not a tensor library and does not improve the S2S numerical kernel by
itself. The finite mathematical operators remain pure numeric code behind a
typed oracle/accelerator port.

## Functional core / Effect shell

The smallest useful split is:

| coordinate | first TypeScript responsibility | current boundary |
|---|---|---|
| `H` | immutable role-bearing hyperedges | credit may reference an existing edge; it cannot create topology |
| `W` | fixed-point semantic macro-weight state | one bounded outcome-credit update only |
| `A` | eligible or credited trajectory state | a prior eligible trajectory is required and consumed |
| `F` | immutable registry of typed function-cell IDs | the credited cell must already be registered; execution is future work |
| `Π` | Schema, capability service, budget, provenance field, atomic transaction | syntax, a capability port, and engineering invariants exist; external outcome/provenance verification and a durable adapter remain open |

The pure kernel is `evolve(state, command)`. It has no I/O, clock, randomness,
retry, or process execution. The Effect shell decodes `unknown`, snapshots the
accepted command, authorizes its capability through a service, and sends the
command to one atomic store transaction. The in-memory store keeps state and
journal in the same `Ref` and changes both through one pure `Ref.modify`.

A persistent adapter must preserve the same contract with a real atomic
compare/evolve/append transaction or an append-only log as the sole source of
truth. Performing an external append and then changing an unrelated in-process
reference is not an acceptable durable implementation.

## What the first slice proves—and does not prove

The first slice currently demonstrates only these engineering properties:

1. strict TypeScript and a single Effect v3 dependency family;
2. an opaque ASCII identifier boundary for cross-runtime replay;
3. exact-schema rejection of excess and malformed input;
4. an existing-`H`/existing-`F`/eligible-`A` precondition for a `W/A` credit
   transition;
5. separate event idempotency and external outcome identity;
6. a capability-service port rather than an authority literal in the domain
   transition; the current static allowlist is test/config scaffolding, not
   identity authentication;
7. one atomic in-memory state-plus-journal transition under concurrent calls;
8. typed failures and immutable snapshots.

It does **not** prove that an external outcome is true, that provenance is
cryptographically authentic, that `W` learned a useful set-to-set operator, that
topology learning works, or that the whole HSWM loop is causally effective. No
scientific status is promoted by adding the package or passing its tests.

## Migration gates

The production path should advance only through these bounded gates:

1. **Contract gate** — freeze TypeScript Schemas for state, events, errors, and
   replay; add migration/version semantics.
2. **Oracle parity gate** — call the frozen Python numeric reference through a
   typed, scoped adapter and compare exact fixture/receipt projections.
3. **Durability gate** — implement an atomic persistent `CommitStore`, crash
   recovery, outcome-unknown reconciliation, and replay.
4. **Function-cell gate** — introduce scoped LLM/tool cell execution with
   bounded concurrency, timeout, cancellation, and typed provider errors.
5. **Learning gate** — bind independently verified outcomes and causal credit to
   candidate `ΔW/ΔH`, then retention/canary/removal validation and rollback.
6. **Authority gate** — only after parity and replay may TypeScript become the
   source of truth for a migrated path; Python remains an independent oracle for
   as long as it adds falsification value.

There should be one executable composition root and therefore one production
`Effect.runPromise` boundary. Library and domain files must not start their own
runtimes. Retry is limited to explicitly transient, idempotent effects; learning
transactions are never blindly retried after an unknown commit outcome.

## Verification

The local package contract is:

```sh
cd src/hswm/effect-runtime
npm ci --ignore-scripts --no-audit --no-fund
npm run verify
```

`@effect/language-service` is pinned for editor diagnostics. Plain `tsc` does
not execute that language-service plugin, so CI must currently be described as
strict TypeScript checking—not Effect-specific compiler diagnostics.

The TypeScript package is a deliberate npm artifact and is not silently placed
inside the Python wheel or sdist. The two artifacts will meet only through
versioned ports and replay contracts.

## Current SWM-0W-S2S control-plane checkpoint

The first S2S `Π` control/evidence slice and opaque Python numeric-oracle
boundary now exist in the working implementation. Six independently reproduced
source, chronology, accounting, and artifact-boundary blockers—and follow-on
Git replace/graft/environment identity bypasses found during repair—are closed
on exact audited bytes. The slice nevertheless remains
`BLOCKED_PRE_PREREG / SCIENTIFIC_UNJUDGED` because live adapters and the
three-job chronology do not yet exist; no future pulse or confirmatory run is
authorized. Exact hashes, resolved regressions, protected files, verification
commands, and the ordered continuation path are frozen in the
[`next-session handoff`](../operations/HSWM_SWM0W_S2S_EFFECT_NEXT_SESSION_2026-08-21.md).
Its companion
[`local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v1.json)
records the same boundary without promoting an efficacy claim or implying a
remote KG write.
