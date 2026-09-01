# HSWM GE-2 and LE-0 local engineering implementation

> **Status:** `SECONDARY_AI_ENGINEERING_IMPLEMENTATION / GRAPH_TRANSACTION_ENGINEERING_ONLY / LOOP_CONTROL_ENGINEERING_ONLY / SCIENTIFICALLY_UNJUDGED`
>
> **Date:** 2026-09-01
>
> **Target authority:** [HSWM Constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md) and [HSWM Adaptive Research Strategy](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)
>
> **Predecessor:** [graph and loop engineering synthesis](HSWM_GRAPH_AND_LOOP_ENGINEERING_SYNTHESIS_2026-09-01.md)

## Answer first

`GE-2` and `LE-0` are now implemented as a bounded local research-control
slice. The implementation does not create a second HSWM or a static cognitive
rulebook: canonical graph state is still owned by the existing schema-relative,
predecessor-bound durable runtime. The new controller records the research
loop around that state and calls the durable runtime only after its declared
snapshot, verifier verdict, evidence descriptors, and graph-delta preconditions
have passed.

## Conceptual delta

Before this change, canonical graph mutation, compiled graph readout, outcome
artifacts, retry/stop decisions, and restore controls existed in useful but
separate slices. The new delta is a source-bound engineering contract:

```text
trigger -> exact recovered graph snapshot -> sealed action artifact
-> separately identified verifier outcome -> delta intent
-> durable CAS commit / reject / quarantine -> restore or terminal verdict
```

The controller makes this sequence replayable and bounded. It does not infer
that an action, outcome, credit descriptor, or authorization descriptor is
true, independent, or a canonical Permit.

## Implemented contract

The implementation is
[`canonical-atom-v2-graph-loop-engineering.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.ts).

| concern | implemented behavior | explicit boundary |
|---|---|---|
| source graph | Captures the existing local POSIX durable RDF projection, schema binding, state digest, journal head, and revision in one loop snapshot. | It is a locally observed journal prefix, not global anti-rollback or distributed truth. |
| loop state | A private create-only local control journal stores a canonical-JSON, predecessor-hash-linked event sequence. | It is research-harness state, never canonical HSWM state or cognition. |
| verification | `actorId` and `verifierId` must differ; an action must be sealed before an outcome may be accepted, retried, or rejected. | Address separation is declared role separation, not proof of outcome independence. |
| budget and stop | Positive bounded action and attempt budgets; retry requires an explicit retry/quarantine verdict; terminal stop or human escalation is recorded. | The controller does not run tools or an LLM autonomously. A caller supplies the bounded action and verifier artifact. |
| delta intent | Requires a current accepted outcome, content-readable trajectory/outcome/credit/authorization/invariant descriptors, a source-matched schema/revision/read-set, and CAS conflict policy. | The authorization label is `REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT`; it cannot be reinterpreted as Permit or `Inv`. |
| conflict and quarantine | A stale snapshot is recorded as `DELTA_INTENT -> QUARANTINED` before any mutation. A later runtime CAS conflict is also quarantined. | A quarantine is not a scientific negative result or a successful rollback. |
| commit | Mutation calls only `CanonicalAtomV2DurableRuntime.submit`; its content, pure-schema, predecessor, and durable journal checks remain authoritative. | The current generic runtime is local predecessor-bound durability, not consensus or a causal-learning admission. |
| restore | A restore requires the exact committed transaction id, a fresh graph snapshot, read access to each named original atom, and a write with byte-identical original payload. | It establishes exact payload restoration in this substrate, not held-out behavioral restoration. |

The current generic canonical runtime refuses a non-null `traceRef`. The
controller therefore refuses rather than bypasses that condition. Its sealed
trajectory is a separately content-addressed engineering artifact until the
later canonical trace/admission contract exists.

## Standard imports used conservatively

There is no settled formal standard called “loop engineering.” This slice uses
the following limited imports:

- [RDF Dataset Canonicalization 1.0](https://www.w3.org/TR/rdf-canon/) informs deterministic, content-addressable graph evidence; it does not confer authority or anti-rollback.
- [SHACL 1.2 Core](https://www.w3.org/TR/shacl12-core/) motivates explicit structural-validation reports; its full qualification remains future work.
- [Kubernetes controllers](https://kubernetes.io/docs/concepts/architecture/controller/) supplies the observed-state/reconciliation analogy, adapted here to a bounded stop/retry/escalate research controller rather than a perpetually converging desired-state system.
- [Loop Engineering: Building Blocks, Adoption, and Impact](https://arxiv.org/abs/2608.21884) supports the emerging practice vocabulary of trigger, persistent state, verifier separation, budget, machine-checkable stop, and human escalation. It is an exploratory study, not a normative standard.

## Verification performed

The local test proves only the following engineering properties:

1. A graph replacement follows trigger, sealed action, distinct verifier
   outcome, source-bound delta, and durable commit; an exact original payload
   can then be restored through a fresh canonical transition.
2. An external competing transition makes the first snapshot stale; the
   proposed delta is quarantined and does not mutate canonical state.
3. Self-verification and exhausted retry budgets are rejected.
4. The control journal rejects tampered canonical event bytes during recovery.

Run it with:

```bash
cd src/hswm/effect-runtime
npm run check
npx vitest run test/canonical-atom-v2-graph-loop-engineering.test.ts
```

No material research result, causal credit, world-model benefit, or HSWM
efficacy is claimed by these tests. `GL-1` still requires its pre-registered
independent outcome, matched alternatives, remove/restore behavioral controls,
and the existing G0–G6 order.
