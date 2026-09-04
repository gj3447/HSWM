# HSWM G0 TypeScript/Effect phase-kernel boundary

> **Date:** 2026-09-04
>
> **Status:** `ENGINEERING_PARITY_SLICE / BLOCKED_EXTERNAL / NOT_CUT_OVER`
>
> **Scientific status:** `NOT_PREREGISTERED / NOT_EXECUTED / G0_NOT_PASSED / G1_LOCKED`
>
> **Claim ceiling:** phase-transition-result parity and a blocked descriptor-only
> control boundary only; not wire compatibility, timeout or signal-queue
> execution, completion-audit equivalence, outcome truth, G0, Permit, canonical
> admission, causal credit, learning, or an HSWM efficacy result.

## 1. Target role and conceptual delta

The target identity does not change. HSWM remains one token-native
LLM-function macro-neural network whose evolving hypergraph is simultaneously
its living harness, world model, and continuous learner. G0 is an evidence-
integrity prerequisite for the later outcome-bound causal-learning loop; G0
orchestration is not itself cognition or learning.

This change introduces one deliberately bounded candidate implementation
boundary:

- TypeScript/Effect now owns strict ingress, an immutable process-local phase
  projection, fail-closed transition results, and the frozen one-shot policy
  projection.
- The current Python workflow remains the authoritative execution-side
  contract while migration parity is incomplete.
- The Python reducer now checks an existing terminal state before validating a
  later payload, so every post-`SEALED` ingress is `TERMINAL_REENTRY` and no
  malformed later ingress can rewrite the first `VOID` reason.
- The Temporal worker, exact-byte integrity and completion replay, qualified
  Cosign audit, and publication eligibility remain behind implementation-
  neutral readback ports.
- No canonical atom kind, ontology, owner registry, Permit path, or learning
  transition is added or changed.

This is therefore a candidate route change, not two authoritative workflow
owners. A live scientific occurrence must continue to use the checked-in
Python boundary until every cutover gate in section 7 is closed and independently
reviewed.

## 2. Implemented Effect boundary

`src/hswm/effect-runtime/src/g0-occurrence-phase-kernel.ts` provides:

1. strict Effect Schema ingress for the occurrence UID, content descriptors,
   bounded occurrence timeout, phase, pulse relation, and transition;
2. module-issued, deeply frozen state handles that reject caller-fabricated
   structural state;
3. the ordered phase sequence
   `REGISTERED -> CLAIMED -> SCHEDULED -> PRE_PULSE_SEALED -> PULSE_VERIFIED
   -> REVEALED -> DUAL_EVALUATED -> SEALED`;
4. terminal `VOID` on duplicate/retry, late evidence, wrong order, malformed
   descriptor, or terminal re-entry, with the first `VOID` immutable;
5. a one-shot policy projection binding reject-duplicate, one workflow
   attempt, one activity attempt, no replacement round, the occurrence timeout,
   60-second finalization grace, eight pending signals, and signal-only
   post-start evidence;
6. a narrow one-shot workflow receipt port and an implementation-neutral
   integrity/completion receipt port;
7. a production default Layer in which both external ports fail with
   `PORT_BLOCKED`; and
8. `SEALED` or `VOID` terminal descriptor readback that accepts only distinct
   digests under the declared `temporal_terminal_audit_receipt` and
   `final_terminal_receipt` roles.

The public package root does not export the test-only in-memory port Layer or
the pure parity helpers. No port has an execute, signal, endpoint, credential,
canonical-write, Permit, admission, or publication method.

## 3. Exact responsibility split

| Boundary | Current responsibility | Not established here |
|---|---|---|
| Effect phase kernel | Strict internal TypeScript ingress, issued immutable state, transition-result parity, one-shot policy values, blocked typed receipt ports | Temporal start, deadlines, queue processing, sender authorization, completion judgment, durability |
| Python `occurrence_workflow.py` | Current authoritative pure phase contract and parity oracle | External execution or outcome truth |
| Python Temporal worker | Exact snake-case wire parsing, deadline-to-`VOID`, bounded pending-signal queue, overflow handling, activity validation with no retry, final queued-signal handling | Singleton authority, external policy enforcement, completion audit |
| Python integrity/completion boundary | Exact evidence bindings, `PENDING_EXTERNAL_AUDIT` candidate, exact candidate digest at `SEALED`, full history replay, qualified Cosign audit, final terminal receipt | Outcome truth, G0 promotion by itself, learning |
| External operator and independent auditor | Credentials, endpoints, separate control domains, private holdout, live service qualification, execution and signed evidence | Repository or handoff storage of secrets/private material |

The module-scoped state identity is only an in-process invariant guard. It is
not durable state, authentication, distributed exactly-once execution, or a
rehydration format.

### 3.1 Graph-engineering interpretation

| Projection element | Typed graph meaning | Claim boundary |
|---|---|---|
| occurrence state | One ordered process-local view of an occurrence UID and phase | Not a canonical atom or durable source of truth |
| `evidenceSha256s` | Ordered content-addressed references carried across transitions | Proves neither artifact availability nor semantic validity |
| transition | A phase, pulse-relative timing class, and evidence descriptor joined as one exact ingress shape | Not a causal edge or outcome judgment |
| Effect port | One explicit responsibility boundary for workflow readback or integrity/completion readback | No generic write, execute, Permit, or learning capability |
| terminal descriptors | Role-bound references to external workflow-audit and final-completion artifacts | Shape, role, and digest separation only; Python still checks exact bytes and lineage |

RO-Crate and OpenLineage remain terminal export projections from the existing
publication boundary. They are not imported as native phase state, and no new
ontology is added merely to mirror this code.

## 4. Parity boundary

The shared fixture
`_research/g0_occurrence/HSWM_G0_WORKFLOW_PARITY_VECTORS.v1.json` contains 11
transition-result cases consumed independently by Python and TypeScript:

- happy path;
- repeated phase;
- reused evidence digest;
- late pre-pulse seal;
- out-of-order phase;
- unknown phase;
- unknown pulse relation;
- invalid evidence digest;
- valid post-seal terminal re-entry;
- malformed post-seal terminal re-entry; and
- immutable first `VOID`.

This is semantic transition-result parity only. The TypeScript internal schema
uses `nextPhase` and `mediaType`; the live Python adapter uses `next_phase` and
`media_type`. The fixture performs an explicit test mapping and does not claim
raw JSON, canonical-byte, or production-wire compatibility. It also does not
test the Temporal deadline loop, pending-signal queue, signal overflow,
authenticated signal admission, or the completion handshake.

## 5. Dependency and standards decision

The slice adds no dependency. The package already pins:

- `effect@3.22.1`, with npm-lock integrity
  `sha512-TNoXushmPOBAjJlthF5d2QwnX2xBPEtcNJr5XKNKbRLbDvBcOYkXlYDfvGfSA0zriwLFuCll5MDtNMAdZL17PQ==`
  and MIT license;
- `typescript@5.9.3` with `strict`, exact optional properties, unchecked-index
  checks, unused checks, and Effect language-service diagnostics; and
- Node `24.13.0` as the package engine.

Effect 3.22.1 is the stable v3 line selected for this repository. The official
[Effect installation guidance](https://effect.website/docs/v3/getting-started/installation/)
requires strict TypeScript and supports Node, Deno, and Bun.

No TypeScript Temporal SDK is added. Temporal's official
[TypeScript SDK guide](https://docs.temporal.io/develop/typescript/) is a vendor
interface, not a graph interoperability standard, and a worker installation
would introduce a materially larger runtime dependency and build surface. The
existing isolated `temporalio==1.32.0` Python worker remains pinned until the
external operator qualification and the migration cutover gates justify a
replacement.

## 6. Local verification

These checks validate engineering behavior only:

```bash
cd src/hswm/effect-runtime
npm run check
npx vitest run test/g0-occurrence-phase-kernel.test.ts test/public-api.test.ts
npx vitest run --exclude test/s2s-live-python.test.ts --maxWorkers=4
npm run build
npm run build:dnrd

cd ../../../..
uv run --locked --extra dev pytest -q \
  tests/test_occurrence_workflow_parity_vectors.py \
  tests/test_occurrence_workflow.py \
  tests/test_occurrence_temporal_worker.py
```

Passing these checks cannot change `G0_NOT_PASSED`.

At this checkpoint the second Vitest command passes 811 tests. The unexcluded
full suite has two pre-existing fail-closed failures in
`test/s2s-live-python.test.ts`: the historical S2S source-closure pin rejects
the currently committed `pyproject.toml` bytes as
`LOCAL_SOURCE_CLOSURE_DRIFT`. This G0 change does not alter either file or
rewrite that hash-bound historical record.

## 7. Cutover gates

TypeScript/Effect may become the authoritative live G0 orchestration boundary
only after all of the following are implemented and independently reviewed:

1. a versioned, strict, byte-tested Python-wire to TypeScript mapping with no
   silent field or role loss;
2. Effect Clock and bounded queue behavior matching deadline, overflow,
   no-retry, and post-seal pending-signal semantics;
3. an authenticated external signal-admission policy binding without placing
   credentials or endpoints in repository state;
4. the exact `PENDING_EXTERNAL_AUDIT` candidate-digest-to-`SEALED` handshake,
   complete history replay, terminal audit receipt, and qualified Cosign check;
5. a durable recovery authority replacing the module-local state identity,
   with explicit duplicate and unknown-outcome behavior;
6. exact artifact/version/integrity/license qualification for any newly
   adopted SDK or binary; and
7. an independent mathematical/protocol review followed by a single cutover
   decision that removes Python from authoritative orchestration rather than
   silently operating two sources of truth.

Until then, this phase kernel is an engineering migration instrument. It is
not a live occurrence runner and creates no material research result, research
receipt, or `F1_R8_RESULTS_LOG.md` entry.
