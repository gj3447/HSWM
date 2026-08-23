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

The present delta is entirely in `Π`. It does not change `H`, `W`, `A`, or `F`,
does not close the outcome-bound causal-learning loop, and is therefore not HSWM
scientific progress by itself. It makes the future S2S measurement boundary more
faithful to the target identity by preventing transport, chronology, or caller
assertions from being mistaken for a learned-world-model result.

The working implementation now adds five bounded engineering pieces:

1. confirmatory event schema v2 and operational-policy v2 separate a job's own
   candidate/adjudication production from later job-completion and artifact
   readback evidence; the policy's seven VOID reasons and Schema literal are
   derived from one tuple and bind resource-policy SHA-256
   `7e4d7252962e53d70f4e74b5117338ced55a645c431e9173256de9f514043ad9`;
2. canonical predecessor-linked journals and a private POSIX file store recover
   exact prefixes after restart, use create-only compare-and-set publication,
   require directory-durability confirmation even on byte-equal retries, reject
   symlinks, gaps, forks, truncation, and oversize files, and return defensive
   snapshots;
3. a shell-free bounded subprocess runner snapshots data inputs once and kills
   and reaps the whole process group on timeout, cancellation, or output-limit
   failure; the first Python layer invokes a rehashed open executable FD,
   preserves its reviewed venv `argv0`, uses a private scoped bytecode-cache
   root, and remains limited to the oracle-source/runtime-import/frozen-golden
   preflight;
4. a strict seekable ZIP reader validates the exact stored-entry dialect used by
   the pinned `actions/upload-artifact` v4.6.2 producer, including central/local
   agreement, signed data descriptors, CRCs, Unix regular-file metadata, exact
   member rosters, and byte caps; and
5. a pure structural job-sequence boundary reconstructs isolated registration,
   candidate, and adjudication carriers at event counts `1 -> 6 -> 9`, validating
   every predecessor ZIP and member binding before emitting the next upload
   plan.

The sequence deliberately stops at event 9. A review demonstrated that an
arbitrary ASCII candidate plus a caller-authored, self-consistent adjudication
document could otherwise reach event 10 and expose `PASS` without the real
Python replay or authoritative GitHub observations. Consequently there is no
production finalizer or verdict-bearing composition function. The event-10
transition remains only in the closed target-state model for a later trusted
composition root.

This checkpoint still proves no candidate numerics. The golden verifier is a
runtime/source compatibility preflight, not evidence that `confirm` or
`adjudicate` ran on a particular candidate, and it does not yet pin the full
imported dependency closure. Direct pre-stage VOID job IDs and their evidence
digests are also caller-supplied observations in the pure model; they are not
authoritative GitHub evidence. Likewise, one supplied candidate readback cannot
prove that a later requery and redownload independently occurred.

The slice therefore remains
`BLOCKED_PRE_PREREG / ENGINEERING_ONLY / SCIENTIFIC_UNJUDGED`. The remaining
authority work is a single Effect composition root that directly owns GitHub
run/job/artifact observations, independent readbacks, verified future-pulse
input, and fixed `confirm`/`adjudicate` Python executions before an external
finalizer may append event 10. No future pulse was selected and no confirmatory
run was dispatched. Exact continuation order and current verification evidence
are recorded in the
[`next-session handoff`](../operations/HSWM_SWM0W_S2S_EFFECT_NEXT_SESSION_2026-08-21.md).
The existing
[`v1 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v1.json)
is retained as a hash-bound historical checkpoint rather than rewritten to
describe this later engineering slice.

The subsequent bounded-adapter implementation and its remaining authority
gates are recorded without changing that history in the
[`2026-08-22 continuation handoff`](../operations/HSWM_SWM0W_S2S_EFFECT_NEXT_SESSION_2026-08-22.md)
and
[`v2 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v2.json).
Those artifacts remain `ENGINEERING_ONLY / SCIENTIFIC_UNJUDGED` and do not
authorize preregistration, future-beacon selection, dispatch, or event 10.

The subsequent request-provenance and registration-B capability checkpoint is
recorded in the
[`authority continuation handoff`](../operations/HSWM_SWM0W_S2S_EFFECT_AUTHORITY_NEXT_SESSION_2026-08-22.md)
and
[`v3 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v3.json).
It preserves the same scientific nonclaims: current-run/dispatch authority,
workflow composition, durable external evidence, and event 10 remain open.

The subsequent workflow-identity and process-local invocation-authority
checkpoint is recorded in the
[`invocation-authority continuation handoff`](../operations/HSWM_SWM0W_S2S_INVOCATION_AUTHORITY_NEXT_SESSION_2026-08-22.md)
and
[`v4 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v4.json).
It advances only the `Π` control boundary. The actual workflow bytes and
source-manifest hash, unique current-run observation, run/stage capability,
durable envelope, finalizer, and scientific verdict remain open.

The next implementation contract is frozen, without claiming implementation,
in the
[`observation-authority design handoff`](../operations/HSWM_SWM0W_S2S_OBSERVATION_AUTHORITY_DESIGN_NEXT_SESSION_2026-08-22.md)
and
[`v5 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v5.json).
It keeps the user-directed strict TypeScript/Effect v3 functional runtime,
specifies raw-byte observation recomputation and the bounded
workflow-runs-for-head query, and separates internal receipt consistency from
GitHub origin and unique-run authority. It changes no `H/W/A/F`, does not close
the outcome-bound causal-learning loop, and leaves production issuance
fail-closed while workflow source bytes are absent.

That v5 contract is now implemented and adversarially verified at code
checkpoint `98f9e7c` as recorded in the
[`observation implementation handoff`](../operations/HSWM_SWM0W_S2S_OBSERVATION_AUTHORITY_IMPLEMENTED_NEXT_SESSION_2026-08-22.md)
and
[`v6 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v6.json).
The private validators lazily reconstruct run, attempt-one jobs, and
workflow-runs-for-head observations from retained bytes, while the new exact
head-SHA endpoint preserves zero/one/multiple rows. This advances only `Pi` and
establishes internal byte/receipt consistency, not GitHub origin, unique
current-run authority, learned `W`, or scientific efficacy. The next bounded
slice is the private request-distinct run-authority Layer, with positive
issuance still closed while workflow source bytes remain OPEN.

The next current-run acquisition and policy slice is implemented at code
checkpoint `dd381f3` and recorded in the
[`current-run authority implementation handoff`](../operations/HSWM_SWM0W_S2S_RUN_AUTHORITY_IMPLEMENTED_NEXT_SESSION_2026-08-22.md)
and
[`v7 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v7.json).
It cross-binds genuine process-local registration and invocation capabilities,
performs the sequential request-distinct run/jobs/head-roster/run bracket with
immediate retained-byte revalidation, and enforces the fixed three-stage job
policy in a closed Effect Layer graph. The positive probe returns only `void`
and never invokes the capability issuer, while production stays
`WORKFLOW_SOURCE_BYTES_OPEN` and performs no GitHub calls. This advances only
`Pi`: it does not prove GitHub origin, issue a genuine current-run capability,
select the production API path representation, create durable replay
protection, or establish learned `W` or scientific efficacy.

The following finite stage-artifact permit slice is implemented at code
checkpoint `01b96ae` and recorded in the
[`stage-artifact permit implementation handoff`](../operations/HSWM_SWM0W_S2S_STAGE_ARTIFACT_PERMITS_IMPLEMENTED_NEXT_SESSION_2026-08-22.md)
and
[`v8 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v8.json).
It replaces caller-selected artifact identity with fixed lazy Effect values,
derives atomically spent permits from the current-run authority, carries the
four bracket receipts into one bounded non-evicting ledger, and independently
rereads the candidate. Its production claim is limited to one trusted
process/module identity slot and remains dormant while workflow bytes and API
path selection are OPEN. This advances only `Π`; it is not durable replay
protection, GitHub-origin evidence, learned `W`, or scientific efficacy.

The following structural durable-evidence substrate is implemented at code
checkpoint `8936487` and recorded in the
[`durable-evidence substrate handoff`](../operations/HSWM_SWM0W_S2S_DURABLE_EVIDENCE_SUBSTRATE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and
[`v9 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v9.json).
It adds canonical predecessor-linked stage envelopes, bounded attachment and
manifest content objects, and one create-only B/stage claim anchor on a
caller-provisioned shared POSIX root. This advances only `Π`. It does not yet
fix the complete replay attachment profiles, close stage programs or upload
postconditions, deploy external storage, establish GitHub origin, or create a
scientific result.

The replay-prerequisite slice is implemented at code checkpoint `443f17f` and
recorded in the
[`replay-prerequisite handoff`](../operations/HSWM_SWM0W_S2S_REPLAY_PREREQUISITES_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and
[`v10 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v10.json).
It pins the packaged protocol configuration, retains current-run,
preregistration, raw drand-pulse, and Python RSS replay inputs, unifies the
GitHub/adjudication byte caps, and fixes the top-level healthy-success
attachment rosters. This advances only `Π`. The rosters are not complete replay
evidence until artifact lookup traces, the full registration source snapshot,
nested schemas and cross-bindings, failure/VOID profiles, closed stage
programs, mandatory upload postconditions, external storage, and the terminal
finalizer are implemented.

The bounded successful-lookup trace and shared current-run Layer slice is
implemented at code checkpoint `91b1153` and recorded in the
[`lookup-trace/shared-Layer handoff`](../operations/HSWM_SWM0W_S2S_LOOKUP_TRACE_SHARED_LAYER_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and
[`v11 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json).
Poll-one, poll-two, and poll-three success now preserve every raw lookup
observation used by classification, and a root-private combined Effect Layer
can, within one build, supply replay plus fixed artifact reads from one
current-run service node. This advances only `Π`. It is not durable replay
evidence or live bearer issuance. Before a stage-read replay schema is
implemented, its byte model must resolve the 75 MiB worst-case candidate read
against the current 16 MiB profile and 64 MiB per-attachment envelope limits.

The bounded stage-read replay core is implemented at code checkpoint `955beb0`
and recorded in the
[`stage-read replay-core handoff`](../operations/HSWM_SWM0W_S2S_STAGE_READ_REPLAY_CORE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
and
[`v12 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json).
It resolves the prior byte contradiction by retaining the downloaded archive
as one revalidated content-addressed predecessor reference and encoding exactly
`manifest.json` plus `observations.bin` in a deterministic stored ZIP capped at
12,583,176 bytes. A strict unknown-input `Either` core and lazy typed Effect
shell reconstruct all retained observations, revalidate the source chain,
archive, members, download and permit receipts, and bind candidate FIRST/REREAD
through one current-run receipt and an exact permit-ledger prefix. This advances
only `Π`. Recovered getters and attachment readers remain an unbranded callable
boundary; the aggregate hostile/every-phase matrix, production stage emission,
external durable root, GitHub origin, genuine capabilities, and all scientific
claims remain OPEN.

The reserved-slot durable replay-profile vertical slice is implemented at code
checkpoint `8d9f254` and recorded in the
[`durable replay-profile integration handoff`](../operations/HSWM_SWM0W_S2S_DURABLE_REPLAY_PROFILE_INTEGRATED_NEXT_SESSION_2026-08-23.md)
and
[`v13 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v13.json).
File-store recoveries now carry process-local issuance provenance, selected
predecessor bytes are snapshotted once, and one root-private lazy Effect bridge
prevalidates the fixed `CONFIRM`/`ADJUDICATE` replay slots before one create-only
local commit and exact recovered-byte comparison. One test-only three-stage
chain survives Layer restart and rejects wrong predecessor and swapped replay
operations. This remains a `Π` engineering slice: the other profile attachments,
closed stage programs, mandatory upload postconditions, external durable-root
wiring, GitHub origin, source freeze, future seed, dispatch, and scientific
verdict remain OPEN. The next claim-critical step is a thin non-authorizing
golden/public-seed oracle-to-upload/readback dry run, not an unbounded hardening
program.

That next slice is now audited and frozen, without runtime implementation, in
the
[`golden vertical-composition design handoff`](../operations/HSWM_SWM0W_S2S_GOLDEN_VERTICAL_COMPOSITION_DESIGN_NEXT_SESSION_2026-08-23.md)
and
[`v14 local KG projection`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v14.json).
The strict TypeScript/Effect v3 shell will directly own the existing pinned
Python/NumPy numeric function cell through `S2SPythonGoldenVerifier` and
`S2SPythonNumericExecutor`; the unused generic numeric-oracle port will not
become a second orchestration model. The audit found 48 healthy-success slot
occurrences: 20 already have construct-and-recover validation, 19 have semantic
machinery but no attachment codec, and 9 lack the carrier or source. The next
claim therefore remains a narrow `TEST_ONLY_NON_AUTHORIZING` golden numeric
upload/readback harness, not a complete profile. The audit also found a semantic
type boundary: a local receipt cannot honestly inhabit the production
confirmatory-event or `S2SArtifactEvidence` inputs required by the existing job
sequence. The first harness must use a distinctly versioned test-only artifact,
must not call the production job sequence or durable profile store, must
exact-bind golden-verifier and numeric-executor runtime identities, and must
terminate immediately on numeric `VOID`. Its fresh Layer must reopen the same
explicit caller-owned temporary file root; no in-memory recovery is claimed.
Because the shallow success-profile validator does not inspect nested bytes, the
harness provides no adapter or call site that relabels its test ZIP as production
evidence. A genuine-authority production
connector, the terminal finalizer, external durability, GitHub origin, source
freeze, future seed, dispatch, event 10, and scientific judgment remain OPEN.
