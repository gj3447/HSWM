# EPWC implementation receipt — S3 certified cut (2026-07-20)

## Verdict

S3 is implemented as two pure modules, not promoted to a durable engine:

1. an immutable, content-addressed `FieldSnapshotV1`; and
2. a certificate-bound readout admission function with payload-free typed
   refusal and a same-snapshot static fallback for traversal certified OFF.

The revised conformance comparison passed. On 40 valid controls, both the
explicitly non-deployable probe and CRE matched an independent legacy oracle
bit-for-bit and reproduced a locked golden digest. Ten scope-fault predicates
were each exercised over 8 queries × 5 policies (400 invocations): CRE returned
no payload, emitted the expected typed refusal, and made zero calls to an
independent instrumented kernel counter in every invocation. Nine additional
self-consistent mutant attacks were counted once each and also refused
pre-kernel.

This is strong local conformance evidence for the tested boundary, not an
exhaustive security proof. It does **not** establish smart-hypergraph efficacy,
cryptographic certificate authenticity, crash-safe revision replay, or
production safety.

## Implemented boundary

### Immutable field snapshot

`field_snapshot.py` binds all of the following into `snapshot_id`:

- verified `WorldArtifactV1.build_id`;
- stable entity and target IDs in their exact dense numpy order;
- frozen little-endian float64 embeddings and field arrays;
- frozen incidence offsets and member indices;
- embedding producer, model revision, configuration digest, and dimension;
- the opaque S3 revision cut and bit-exact target salience vector;
- kernel version, live callable/source/build digest, semantic mode, bilinear
  matrix shape/content, and `lambda_b`;
- field/tie/projection policy and candidate order; and
- topology, embedding-manifest, parameter, policy, and material digests.

The snapshot stores bytes rather than a mutable `Hypergraph` or `WeightField`.
Hydration occurs only after verification and produces a short-lived legacy
field. `WeightField(..., target_emb=...)` replaces the previous private
`_pooled` monkeypatch without changing the numerical order of operations.

`score_components(...)` emits per-target cosine, semantic residual, temporal
delta, traversal residual, final score, and a component digest. Static reads
carry a zero traversal residual. A μ>0 APPLY read reconstructs the full executed
score vector and records the measured `W_trav - W_static`; payload scores must
be bit-identical to their component finals or the read raises internally.

### Certified readout admission

`certified_readout.py` binds one exact tuple:

```text
(world, snapshot, embedding model/config, revision cut,
 kernel/parameters, field policy, candidate set, readout policy)
```

The production-facing path takes no loose `k`, temperature, `mu`, `gamma`, hop,
or trip-wire knobs. Those values live in a content-addressed readout policy.
It verifies request, trusted certificate ID, monotonic generation interval,
snapshot integrity, query embedding contract, and every scope field before
invoking a scorer.

Refusals contain no rank, score, probability, or target payload and record
`kernel_invoked=False`. An `OFF` certificate authorizes only a traversal
fallback to the static scores from the *same* verified snapshot. World, model,
revision, policy, or snapshot mismatch never falls back.

Static field, readout, and traversal source/live-callable ABI digests are bound,
so an implementation mutation invalidates an existing snapshot or policy. The
certificate is a local scope/admission receipt. Trust is an explicit
certificate-ID allowlist; there is no signature or distributed trust claim.

## Deterministic conformance comparison

Fixture:

- 8 queries;
- 5 targets;
- 5 policies: retrieve k=1, retrieve k=5, selection temperature=1, dispatch,
  and traversal floor (`mu=0`, `gamma=.5`, two hops, `kappa=1`); and
- 10 scope-fault predicates, each repeated over the 40 query/policy cells; and
- 9 distinct adversarial mutants, counted once each rather than inflated by
  repetition.

| scope fault | expected refusal | probe payloads | CRE payloads |
|---|---|---:|---:|
| foreign world | `world_field_mismatch` | 40 | 0 |
| same world, reversed dense layout | `field_snapshot_mismatch` | 40 | 0 |
| query model revision | `model_revision_mismatch` | 40 | 0 |
| query model config | `model_config_mismatch` | 40 | 0 |
| field parameter/policy | `field_policy_mismatch` | 40 | 0 |
| readout policy rotation | `readout_policy_mismatch` | 40 | 0 |
| revision cut | `revision_cut_mismatch` | 40 | 0 |
| torn revision fold | `revision_fold_mismatch` | 40 | 0 |
| untrusted certificate | `invalid_certificate` | 40 | 0 |
| expired generation | `certificate_expired` | 40 | 0 |

The probe column is not a deployable baseline: `research_probe(...)` returns a
different `ProbeResultV1` with mandatory `NOT_DEPLOYABLE` and intentionally
does not check scope. Aggregate receipt: `certified_cut_comparison_result.json`.

```text
valid vs oracle:       probe 40/40, CRE 40/40, golden digest matched
scope-fault calls:     10 predicates x 40 cells = 400 invocations
CRE scope payloads:      0/400
CRE typed refusals:    400/400, exact expected codes
observed kernel calls:   0/400
unique mutant attacks:   9/9 refused, zero payload, zero kernel calls
```

The 40 positive controls prevent a reject-everything implementation from
passing. The independent oracle and locked digest prevent the probe and CRE
from jointly defining their own truth. Expiration uses a validated non-negative
integer generation, never wall clock time.

The nine mutant attacks cover malformed bilinear shape, unknown certificate
status, NaN generation, malformed query vector, unsupported field policy,
negative revision, live static-kernel mutation, live traversal-kernel mutation,
and live internal readout-compute mutation.

Three traversal safety controls also passed: an actual μ>0 APPLY emitted 16
nonzero residuals with payload/component bit identity; a query-time `n_eff`
trip fell back to current static; and a μ>0 policy certified OFF executed at
μ=0 on the same snapshot.

## Validation

- S3 focused suite: **33 passed**.
- Full repository suite: **118 passed**.
- `git diff --check`: clean.
- Engine/module decision validator: **OK, 0 warnings** for
  `HSWM/HSWM_WORLD_COMPILER_MODULE_DECISION_2026-07-20.json`.
- Wheel-only import verification: **PASS** for `field_snapshot`,
  `certified_readout`, `certified_cut_compare`, `legacy_adapter`, and
  `world_compiler`; the installed-wheel comparison also returned `PASS` with
  zero CRE scope-fault payloads.

## The smart-hypergraph boundary

The user goal remains a **smart hypergraph**, not merely a safe static index.
S3 preserves that lane by binding topology, kernel version, parameters, and the
entire traversal policy into the certificate. A future graph builder/kernel can
therefore be deployed only after its own evidence identifies the exact snapshot
and policy that won.

The present evidence remains negative for current traversal: MuSiQue and 2Wiki
certification selected `mu=0`. S3 correctly makes that result a static fallback;
it does not relabel refusal as intelligence. The current positive result is the
static field's retrieval lift, not successful graph reasoning.

The next smart-graph experiment should hold embedding and offline-judgment
budgets constant and compare:

1. current paragraph/title heuristic graph;
2. NER + coreference + entity-linking graph;
3. bake-time LLM-extracted **n-ary** claims with evidence spans; and
4. the same n-ary graph with canonical entity/relation typing (for example,
   Wikidata-style IDs and SKOS hierarchy), without importing full OWL inference.

Each builder arm must be tested with both static and traversal readouts against
cosine, the current HSWM field, and a strong late-interaction/graph baseline.
Required diagnostics are alias fragmentation, false-merge rate, bridge
coverage, supporting recall/nDCG/downstream F1, trip/abstention rate, and build
cost. Traversal is allowed to turn on only if it beats that arm's own static
field on held-out data without safety collateral.

## Explicit S4 limits

- `RevisionCutV1` is an opaque frozen preimage, not an event-fold proof.
- No duplicate/no-op event semantics, as-of fold, compensation, or concurrent
  snapshot publication exists yet.
- No crash/restart, WAL, durable idempotency, or replay claim exists.
- No cryptographic certificate signatures or revocation distribution exists.
- `research_probe(...)` returns a distinct `ProbeResultV1` carrying mandatory
  `NOT_DEPLOYABLE`; deployable callers must use `read_certified(...)`.
- The 400 invocations cover 10 predicates over 40 cells; they are not 400
  independent fault classes and measure admission conformance, not retrieval
  quality.

Repository state: changes remain intentionally uncommitted and unpushed.
