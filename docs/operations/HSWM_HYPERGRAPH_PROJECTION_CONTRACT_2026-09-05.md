# HSWM Hypergraph Projection Contract v1

Status: `BOUNDED_METADATA_PROJECTION_IMPLEMENTED / FULL_HSWM_NOT_REALIZED`.
Authority: `SECONDARY_AI_ENGINEERING_CONTRACT`; engineering rehearsal only.

The [HSWM constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md) defines one
token-native evolving hypergraph whose state conditions traversal and whose
outcomes may support owner-valid canonical revisions. Neo4j and RDF are bounded
projections of that state. This contract connects the existing Atom v2 RDF
compiler to a Neo4j read model; it does not change the canonical schema,
single-owner obligations, Inv/Permit or outcome-credit admission.

The conceptual change is one reproducible source binding for the two views,
with explicit mapping loss, role/ordinal preservation and content readback.
The FCL-1..8 contracts and `SCIENTIFICALLY_CONNECTED /
INTEGRATED_CLAIM_UNJUDGED` scientific ceiling remain those of the
[fractal scientific connections](../research/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md).
A graph/database test is not evidence of G0, cognition or causal macro-learning.

## Mapping and authority

The executable contract is
[`canonical-atom-v2-hypergraph-projection.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-hypergraph-projection.ts).
Its manifest binds the complete retained source bundle, compiler profile,
N-Quads and property-graph rows with separate SHA-256 digests. Its namespace is
content-addressed from source, profile and RDF output; keys never collapse a
lineage fork into an atom UID alone.

| Canonical source | Property-graph projection |
| --- | --- |
| `(schemaVersion, lineageId, atomUid, revisionId)` | `:HSWMProjectionV1:Atom` with decomposed key, kind, owner, content descriptor and provenance |
| Atom kind with schema `form: RELATION` | The same `:Atom`, additionally labelled `:Hyperedge` |
| Each typed reference array position | `:Participation` with source, target, reference type, role and ordinal |
| Reference connection | `HAS_PARTICIPATION` and `TARGET` relationships through that participation |
| Provenance source atom | `DERIVED_FROM` relationship plus source-key property |
| Compilation | `:ProjectionRun` binding source, schema, tail, profile and RDF output hashes |

Participation is a derived reference view, not a newly admitted incidence atom.
Its evidence and `sourceOwnerUid` explicitly describe the source atom. It has no
independent canonical owner, lifecycle or authorization effect. An incidence
with its own canonical lifecycle must first be admitted through a schema that
defines that atom and its owner. The projector cannot invent it.

Repeated targets under different roles and array ordinals stay distinct.
Trajectory, outcome and revision/disposition atoms remain individually
addressable under their schema-approved kinds. The fixture does not confer
independent outcome custody on its synthetic outcome.

The graph retains atom metadata and typed-reference multiplicity. It omits raw
payload bytes, the full journal, schema constraints, tail-record structure and
state bootstrap/accepted-transition metadata. The full projection bundle retains
the latter metadata through the existing RDF manifest, but still omits payload
bytes and the full journal. Therefore parity means exact agreement within this
declared metadata projection; it is not lossless reconstruction of all HSWM state.

Bundle input has the existing `CALLER_SUPPLIED_SELF_CONSISTENT_BUNDLE_NOT_DURABLE_RECOVERY_ATTESTED`
ceiling. `compileDurableHypergraphProjection` additionally returns the existing
durable RDF recovery witness without promoting it to global-tail completeness,
anti-rollback or independent source custody. Compilers are profile-bound, not
executable-artifact-attested.

## Database behavior

The [Neo4j adapter](../../src/hswm/effect-runtime/src/canonical-atom-v2-neo4j-projection.ts)
uses the official JavaScript driver, an explicit database and fixed parameterized
Cypher templates. Publishing is disabled unless `apply: true`. The CLI's default
mode does not connect to a database.

Publishing checks the supplied bundle, writes only its `HSWMProjectionV1`
namespace, and reads back all nodes, labels, properties, relationship types and
endpoints in the same managed transaction. A mismatch aborts the transaction.
Exact republishing is idempotent. Rebuild deletes only scoped relationships and
nodes, rejects foreign attachments, reconstructs the same graph and compares its
computed digest. Plain node deletion also refuses a foreign attachment introduced
after preflight. Existing canonical/code KG nodes are outside this namespace.

Callers must serialize writes to the same projection ID. This adapter does not
install global uniqueness constraints or claim distributed writer exclusion.
Neo4j session read routing is not database access control. Credentials and server
ACLs determine database permission; no graph property grants canonical permission.
There is no canonical writer, learning callback, arbitrary Cypher executor or new
MCP capability. An analytical finding must enter the existing canonical proposal
and admission workflow before it can change HSWM state.

## Run the bounded rehearsal

From an ordinary Linux checkout with the documented Node/npm and `uv` runtimes:

```bash
cd src/hswm/effect-runtime
npm ci
npm run check
npm run build
npm run projection:rehearsal -- --out /tmp/hswm-projection-local
```

The output directory must be new and its parent must exist. This command compiles
a synthetic Atom v2 journal with a ternary relation, validates its N-Quads with the
existing SHACL 1.0 shapes in the locked graph Python runtime, and emits the
projection, source, graph, RDF, SHACL report, PROV-O, OpenLineage and RO-Crate files.
No G0 success receipt or research-result log is created.

To materialize a projection, supply the existing publisher's flat YAML config
format (`uri`, `user`, `password`, `database`) through a private file:

```bash
npm run projection:rehearsal -- --out /tmp/hswm-projection-live \
  --apply --source-config /absolute/private/neo4j-source.yml
npm run projection:rehearsal -- --out /tmp/hswm-projection-rebuilt \
  --apply --rebuild --source-config /absolute/private/neo4j-source.yml
```

An application can pass its existing schema and source to `compileHypergraphProjection`.
The CLI also accepts `--input hypergraph-projection.json` instead of `--rehearsal`
and verifies the serialized source and outputs by recompilation before use.
The package requires a full repository for its existing Python/SHACL workflow;
`--repository-root` selects that checkout when invoked elsewhere.

The receipt is an execution record. Run UUIDs/timestamps vary between executions;
the source, graph and RDF hashes remain deterministic for unchanged input.
Supplied live readback evidence is explicitly `CALLER_REPORTED_LIVE_NEO4J_PARITY`,
not independent database custody. OpenLineage COMPLETE records completion of this
bounded compiler/publisher operation, not completion of HSWM learning.

## Verification and standards

Local coverage includes ternary/repeated-target roles, fork separation, stale
source and tampered artifacts, scoped rollback, foreign-attachment refusal,
idempotence, receipt validation and real SHACL execution. The opt-in
[disposable Neo4j workflow](../../.github/workflows/hypergraph-projection.yml)
also exercises actual publish, readback and rebuild using a digest-pinned official
Community image. It uses a disposable database and no production credentials.

The application adds official `neo4j-driver` 6.2.0 (Apache-2.0). Package integrity,
source identities, image digest and authority classes are recorded in
[`hypergraph-projection-toolchain.json`](../../src/hswm/effect-runtime/assets/hypergraph-projection-toolchain.json)
and the npm lockfile. n10s is not required by this bounded mapping.

The existing graph-standard suite receipts retain their original bytes and
results. Their exact historical npm manifests are copied from commit
`9445bc9da30d6dc629860cdea896cd1cc61dd5dd` into
[`qualified_node_runtime`](../../_research/graph_standards/qualified_node_runtime/SOURCE.json).
The active acceptance manifest references that frozen qualification runtime.
This preserves reproducibility while the application adds dependencies; it does
not qualify the new Neo4j adapter by association with historical W3C results.

Official sources checked 2026-09-05:

- [Neo4j graph model](https://neo4j.com/docs/getting-started/graph-database/) and
  [managed transactions](https://neo4j.com/docs/javascript-manual/current/transactions/):
  directed binary relationships motivate reified role-bearing participation;
  managed transactions provide bounded atomic writes and readback.
- [RDF 1.1](https://www.w3.org/TR/rdf11-concepts/),
  [SHACL 1.0](https://www.w3.org/TR/shacl/),
  [PROV-O](https://www.w3.org/TR/prov-o/) and
  [JSON-LD 1.1](https://www.w3.org/TR/json-ld11/) remain the stable lane.
- [RDF 1.2 Concepts](https://www.w3.org/TR/rdf12-concepts/) is a Candidate
  Recommendation Snapshot; [SPARQL 1.2](https://www.w3.org/TR/sparql12-query/)
  and [SHACL 1.2 Core](https://www.w3.org/TR/shacl12-core/) remain drafts.
  No 1.2 feature or full GQL conformance is promoted here.
- [OpenLineage facets](https://openlineage.io/docs/spec/facets/) and
  [RO-Crate 1.3](https://www.researchobject.org/ro-crate/specification/1.3/index.html)
  provide execution/artifact descriptions. This implementation reuses the
  repository's pinned artifact facet and core RunEvent schema.
