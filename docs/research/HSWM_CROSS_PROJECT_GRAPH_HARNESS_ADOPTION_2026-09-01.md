# HSWM cross-project graph and harness engineering adoption profile

> **Status:** `SECONDARY_AI_ENGINEERING_PORTABILITY_ASSESSMENT / PROJECT_ADAPTERS_REQUIRED / EFFICACY_UNJUDGED`
>
> **Date:** 2026-09-01
>
> **Authority:** the HSWM Constitution and adaptive research strategy govern
> HSWM only. This document neither changes sibling repositories nor makes the
> HSWM ontology their source of truth.

## 1. Answer first

Graph engineering and harness engineering can be evaluated for reuse across
projects, but the reusable unit must be a **project-neutral profile plus local adapters**.
It must not be an export of HSWM cognition, ontology, permissions, or learning
claims.

```text
project-owned domain state and effect boundary
  -> project-local loss/authority adapter
  -> versioned graph envelopes, deltas, receipts, and harness lifecycle
  -> optional RDF/N-Quads, RDFC, SHACL, PROV-O, or backend adapters
```

Potential benefits include earlier drift detection and, where the local
adapter supplies it, exact replay, explicit unknown outcomes, and smaller
debugging search spaces. Those are design hypotheses until the projects
measure lead time, defect escape, recovery time, and harness maintenance
burden under matched work.

## 2. Canonical role, evidence, and conceptual delta

| layer | statement |
|---|---|
| HSWM target | One token-native LLM-function macro-neural network whose evolving canonical hypergraph jointly plays living-harness, world-model, and continuous-learner roles. |
| reusable engineering profile | A non-cognitive exchange and verification contract for graph snapshots, deltas, effect receipts, recovery, reconciliation, and completion evidence. |
| current evidence | HSWM has a local durable canonical journal and a recovery-bound read-only RDF projection. Sibling projects contain useful but different graph, WAL, receipt, transaction, and harness mechanisms. No cross-project runtime qualification or productivity effect has been run. |
| conceptual delta | Keep domain truth and write authority inside each project. Standardize only the envelope, evidence, failure, replay, and adapter obligations needed to compare or operate implementations safely. |

This avoids two opposite errors: copying HSWM-specific atoms into unrelated
domains, and treating an untyped universal graph as if it preserved every
project's authority, privacy, transaction, and causal semantics.

## 3. Existing project-neutral seed

The nearest reusable seed is the sibling
[`agent-coding-paradigm`](https://github.com/gj3447/agent-coding-paradigm/tree/000d5fd0d40518a700713e55e9167ca07a514189),
not the HSWM ontology. At the audited commit it defines an experimental FLRH
Graph Interoperability Profile and Harness Contract:

| source | audited SHA-256 | bounded import |
|---|---|---|
| [`GRAPH_CONTRACT.md`](https://github.com/gj3447/agent-coding-paradigm/blob/000d5fd0d40518a700713e55e9167ca07a514189/docs/GRAPH_CONTRACT.md) | `99f3d6a060e1e1d65f1a070a00975ec3249adcf03e39e4fd9aa2c86edfe958c7` | Typed graph kinds, identity ladder, immutable revisions, `GraphEnvelope`, `GraphDelta`, and receipt boundaries. |
| [`HARNESS_CONTRACT.md`](https://github.com/gj3447/agent-coding-paradigm/blob/000d5fd0d40518a700713e55e9167ca07a514189/docs/HARNESS_CONTRACT.md) | `644039fcb8984fd57a1472e8026e04837b8bf1ce9eb4baa2135b7987346ce936` | Bounded ingest-to-terminal lifecycle, effect ledger, reconciliation, strong completion predicate, and typed terminal failures. |
| [`protocol.v1.schema.json`](https://github.com/gj3447/agent-coding-paradigm/blob/000d5fd0d40518a700713e55e9167ca07a514189/spec/schema/protocol.v1.schema.json) | `a81a44d3d572cc43bc459adc62374ee261549758e0687263a887a3774a863da2` | Machine shapes for graph envelopes, graph deltas, action receipts, and resolved-composition receipts. Shape validation does not prove runtime behavior. |
| [`run-fsm.v1.json`](https://github.com/gj3447/agent-coding-paradigm/blob/000d5fd0d40518a700713e55e9167ca07a514189/spec/run-fsm.v1.json) | `043d8038f8bf91d7f60c2b57f7fcf788e25684eed6409f184b607fae227537ea` | Experimental harness lifecycle vocabulary and guards. It is not an industry standard and has no general efficacy result. |

The reusable minimum is:

- `GraphEnvelope`: graph kind and revision, schema/profile/canonicalizer,
  content and source-snapshot digests, provenance references;
- `GraphDelta`: immutable base/new revision, additions/deletions commitments,
  causal parents, producer, idempotency key, logical time;
- `ActionReceipt`: intent, authority, input/platform identity, attempt,
  idempotency, output, and confirmed-success/confirmed-failure/unknown outcome;
- `ResolvedCompositionReceipt`: production and harness resolved graphs,
  permitted adapter substitutions, forbidden differences, and independent
  verification;
- a bounded lifecycle from ingest through durable intent, execution,
  reconciliation, completion verification, and a typed terminal state.

Traces remain observations. They cannot be the sole authority for truth,
permission, completion, or causal credit.

## 4. HSWM adapter already applied

HSWM now keeps the following authority split:

| project-neutral concern | HSWM binding | boundary |
|---|---|---|
| source snapshot | the contiguous durable journal prefix returned by one replay-verified recovery observation | The prefix commitment does not prove that a concurrent, deleted, or external later tail never existed. |
| graph content | role-preserving, reified RDF 1.1 N-Quads bytes | Derived read-only view, not canonical HSWM state. |
| schema identity | exact canonical atom v2 schema content descriptor | Schema shape does not establish semantic truth. |
| revision identity | state revision, recovered head, state digest, and ordered-prefix commitment | Local predecessor-bound recovery, not distributed consensus or an external notary. |
| provenance | native atom provenance and journal lineage projected into bounded graph evidence | Not independent causal credit. |
| write path | none | `writeBack = FORBIDDEN`; mutation remains on the Permit-bound canonical transition path. |

The current durable artifact is compatible with the *intent* of a
project-neutral `G_sem` graph envelope: its RDF content digest is the graph
content identity and its observed journal-prefix commitment is the source
snapshot identity. It is not yet declared schema-conformant to the external
experimental FLRH `GraphEnvelope`; that requires a pinned validator and
cross-repository fixture, and it must remain optional.

## 5. Read-only sibling assessment

No sibling repository was modified. The tiers below are adoption order, not a
quality ranking.

| project | observed reusable surface | recommended first adapter |
|---|---|---|
| `agent-coding-paradigm` | Project-neutral graph/harness contracts, Python reference validators, TypeScript/Effect experiments. | Tier 0 pinned reference source for that experimental profile only; keep its non-standard status explicit. |
| `HSWM` | Canonical atoms, Effect runtime, predecessor-bound journal, Permit and evidence boundaries, durable RDF projection. | Tier 1 canonical-state-to-read-only-graph adapter, then official standards qualification and typed graph delta. |
| `SUPULLIM` | TypeScript/Effect, n-ary graph, SQLite WAL, provenance/time, idempotency and reconciliation. | Tier 1 profile adapter while preserving public/community/identity-vault physical separation. |
| `333` | Rust WAL/CRDT/transfer receipts and fault tests. | Tier 1 action/recovery receipt adapter; do not require a graph backend. |
| `ICE_ORCA_DRAGON` | TypeScript/Effect control plane, Python computation, ontology and reproducibility artifacts. | Tier 2 research-run and receipt adapter around selected boundaries. |
| `GAME` | Multiple TypeScript, Rust, and Python subprojects with ontology/recovery artifacts. | Tier 2 opt-in adapters per game; no monorepo-wide universal graph mandate. |
| `metahumotonic_web_back` | Python API, TypeScript KG write port, wiki/ontology surfaces. | Tier 2 publication and KG read/write receipt boundary. |
| `BITCOIN/ttest-*` | Go/Cosmos-EVM state and TypeScript tooling with transaction idempotency concerns. | Tier 2 transaction/effect receipts only unless a domain graph use case is demonstrated. |
| `metahumotonic-web` | Astro static publishing and wiki artifacts. | Tier 3 provenance/readout export only. |
| `bhgman_tool`, `spacegirl_tool` | Python, Lean, and agent research tools. | Tier 3 experiment receipts when a concrete replay need exists. |
| `MIND` | Personal-record material. | Exclude from automatic graphing; sensitive content requires an explicit, narrow authorization. |
| `SERVER` | Operations and infrastructure material. | Exclude by default; production, secret, and deployment boundaries require separate authorization. |

## 6. Per-project adoption gates

A project adapter is admissible only if it answers these questions before a
write or production integration:

1. What remains the project-owned source of truth and responsibility owner?
2. Which graph kind is emitted, and which domain distinctions are lost?
3. Which canonicalizer, schema, resolver, environment profile, and versions
   define digest comparability?
4. Is the adapter read-only, proposed-delta-only, or write-authorized? The
   default is read-only.
5. What durable intent, idempotency, outcome-unknown, reconciliation, and
   recovery evidence exists for external effects?
6. Which privacy, identity, tenant, vault, publication, and secret boundaries
   must never be joined by the graph?
7. Which independent fixture validates production/harness composition rather
   than source-text similarity?
8. Which resource, retry, correction, queue, and no-progress budgets stop the
   harness?
9. What negative and rollback fixtures prove that failure does not silently
   become success?
10. Which metrics will test the claimed development benefit without confusing
    more harness code with faster or better delivery?

Repository source, CI, production runtime, external effects, or graph services
must not be changed from this assessment alone. Each project needs an explicit
scoped implementation decision, its own instructions, and validation against
its current dirty state and authority boundaries.

## 7. Recommended rollout

1. Finish qualification of HSWM's local durable projection with official
   N-Quads/RDFC vectors and its loss/authority manifest as the first concrete
   adapter.
2. In the profile repository, keep neutral schemas and fixtures independent of
   every domain model; add versioned adapters rather than copying contracts.
3. Pilot `SUPULLIM` for graph-envelope/reconciliation compatibility and `333`
   for action/recovery receipts because their existing mechanisms provide
   strong counterexamples to an HSWM-specific design.
4. Measure matched changes with lead time, escaped defects, replay success,
   mean recovery time, unknown-outcome resolution, and static-harness bytes or
   maintenance effort.
5. Adopt only fields and lifecycle stages whose measured benefit exceeds their
   maintenance and interpretation burden. A negative result retires that exact
   adapter family; it does not shrink any project's target.

This rollout makes standard graph formats and rigorous harness evidence
available where useful while keeping every project's semantics, privacy, and
write authority local.
