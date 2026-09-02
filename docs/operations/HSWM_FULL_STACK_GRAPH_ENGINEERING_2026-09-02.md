# HSWM full-stack graph engineering boundary

> **Status:** `IMPLEMENTED_BOUNDED_GRAPH_INTEROPERABILITY / SIX_LOCKED_EXECUTABLE_PROFILES / PARTIAL_REMOTE_INTEGRATION`
>
> **Date:** 2026-09-02
>
> **Target identity:** [HSWM Constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md)
>
> **Machine authority:** [Graph standards acceptance lock](../../_research/graph_standards/HSWM_GRAPH_STANDARDS_ACCEPTANCE.v1.json)

## 1. Outcome and exact scope

The current canonical Atom v2 state now has a bounded, standard-first graph
interoperability stack. It covers deterministic RDF 1.1 N-Quads exchange,
RDFC-1.0 canonicalization evidence, SHACL 1.0 structural validation, JSON-LD
1.1 exchange, a constrained PROV-O envelope, and local read-only SPARQL
`SELECT`/`ASK`. W3C Trace Context parsing and injection is implemented as a
correlation-only carrier.

“All data” does not mean copying every repository file or every payload byte
into RDF. It means every data class crossing this graph boundary has an
explicit route or an explicit exclusion:

| Native data | Graph-boundary treatment |
|---|---|
| Canonical schema binding, current state, atom versions, owner and kind | Included in the source-bound RDF projection. |
| N-ary typed references and their roles | Reified as typed-reference resources with source, target, role, type, and ordinal; not flattened into unlabeled pairwise edges. |
| Content payload bytes | Deliberately omitted; media type, byte length, and SHA-256 descriptor are projected. |
| Full journal history | Deliberately omitted; current state digest and exact tail descriptor bind the projection. |
| Native evidence and provenance assertions | Preserved as projection fields; the PROV-O view describes only derivation of the external view and cannot overwrite native records. |
| Live external data and actions | Remain behind explicit MCP allowlists and authentication. They do not become canonical writes through this stack. |
| Trace headers | Correlation-only at a future real remote boundary; never canonical provenance or causal credit. |
| Property-graph and sparse-compute forms | Not implemented until a concrete backend has a loss and parity contract. |

## 2. Conceptual delta

The change is not a new HSWM subsystem and does not replace the token-native
LLM-function macro-neural network. The target remains one evolving hypergraph
acting as living harness, world model, and continuous learner under the same
typed, outcome-bound dynamics.

The engineering delta is narrower: the existing canonical atom projection can
now be consumed by published graph standards through source-bound read-only
views. There is no reverse edge from an RDF, JSON-LD, SHACL, SPARQL, PROV, MCP,
or trace representation into canonical admission.

```text
canonical Atom v2 schema + state + journal tail  (native authority)
                    |
                    v
       deterministic blank-node-free RDF 1.1 Dataset
                    |
          +---------+----------+-----------+-----------+
          |                    |           |           |
          v                    v           v           v
      RDFC-1.0             SHACL 1.0   JSON-LD 1.1  local SPARQL
   external fixed point    structure    exchange      SELECT/ASK
          |                    |           |           |
          +--------------------+-----------+-----------+
                               |
                               v
                   constrained PROV-O view envelope

Every branch: write-back forbidden; source change invalidates the view.
```

This does not change FCL-1..8, create cognition, establish consciousness or
selfhood, prove scale-invariant causal closure, issue a Permit, assign causal
credit, or demonstrate continuous-learning or LLM efficacy.

## 3. Stable implementation matrix

| Layer | Stable standard and implementation | Enforced boundary | Qualification |
|---|---|---|---|
| Dataset model and syntax | RDF 1.1 + N-Quads 1.1; `n3@2.7.2` | Blank-node-free deterministic named-graph projection, exact manifest and byte digest, no writer | 85/85 attempted approved RDF 1.1 syntax vectors pass. |
| Dataset canonicalization | RDFC-1.0; `rdf-canonize@5.0.0` | External processor only; does not define HSWM identity or signatures | 86/86 attempted approved vectors pass; current HSWM fixture is a fixed point. |
| Structural validation | SHACL 1.0; `pyshacl==0.40.1` + `rdflib==7.6.0` | Projection shape checks cardinality, lexical/range constraints, kind/form alignment, and provenance-mode/source structure | 97/97 attempted used-component Core vectors pass; one unused `sh:uniqueLang` fixture is explicitly excluded. |
| JSON exchange | JSON-LD 1.1; `jsonld@9.0.0` | Actual FromRDF then JSON-LD 1.1 compaction, local context only, remote loader blocked, source/output descriptors | 21/21 attempted exact-profile FromRDF vectors pass; 33 out-of-profile vectors remain exclusions. |
| Query | SPARQL 1.1 local read-only subset; `rdflib==7.6.0` | Only `SELECT` and `ASK`; no update, remote dataset, `SERVICE`, construction, description, protocol, or entailment | 40/40 attempted official backward-compatible basic fixtures pass; all others remain exclusions. |
| Provenance exchange | PROV-O | Source entity → derivation activity → derived view entity; native evidence remains authoritative | Constrained mapping and local tests; no executable official conformance suite is claimed. |
| Distributed correlation | W3C Trace Context | Strict v00 carrier, safe future-version downgrade, validated `tracestate`, all-zero rejection | Local adapter tests pass; real remote propagation is not yet integrated. |

The implementation entry points are:

- [`canonical-atom-v2-rdf-projection.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-rdf-projection.ts) for the native-to-RDF projection;
- [`canonical-atom-v2-jsonld-view.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-jsonld-view.ts) for actual JSON-LD algorithms;
- [`standard_graph_view.py`](../../src/hswm/infrastructure/standard_graph_view.py) for source-bound RDFLib, SHACL, SPARQL, local alias, and PROV-O views;
- [`HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_SHACL_1_0.ttl`](../../schemas/HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_SHACL_1_0.ttl) for the stable projection shape;
- [`trace_context.py`](../../src/hswm/infrastructure/trace_context.py) for the correlation-only HTTP carrier.

## 4. Reproducibility and authority

Every selected independent adapter is labelled `NOT_W3C` and pinned by exact
package version, source tag/commit, registry artifact integrity, license, and
lockfile. Official suites are pinned by repository commit, selected git tree,
deterministic archive digest, manifest digest, and license digest. Runnable
profiles additionally bind the runner and relevant implementation artifact
bytes. The official-suite runners exercise the selected independent engines
directly; the SHACL, JSON-LD, and SPARQL HSWM adapters are exercised by separate
local integration tests. Artifact binding does not mean that an official-suite
runner imported the HSWM adapter.

Node profiles use Node 24.13.0 and npm 11.6.2 with a clean temporary
`npm ci --ignore-scripts` install. Python profiles use CPython 3.12.13 and uv
0.12.3 with `--isolated --locked --no-python-downloads` and the exact `graph`
extra from the dedicated
[`graph_standards/runtime`](../../_research/graph_standards/runtime/) project.
That separate dependency closure preserves the historical root `uv.lock`
byte-for-byte. Receipt verification fails on package, source, artifact,
runtime, count, claim-ceiling, or receipt drift.

```bash
uv run hswm-graph-standards verify
uv run --project _research/graph_standards/runtime --locked --extra graph \
  pytest -q \
  tests/test_graph_standard_tooling.py \
  tests/test_standard_graph_view.py \
  tests/test_trace_context.py

cd src/hswm/effect-runtime
npm run verify
```

`hswm-graph-standards` is repository-bound because the acceptance lock hashes
files from the complete source closure. From an installed wheel, point it at a
full checkout or extracted sdist with `--repository-root` and, when needed,
`--manifest`; it does not pretend the wheel alone contains the npm and research
authority surfaces.

The opt-in
[`graph-standards-requalification.yml`](../../.github/workflows/graph-standards-requalification.yml)
workflow installs the exact locked runtimes, fetches all six source-pinned
official suites, replays every bounded profile, and requires byte-identical
receipts. It is manual because networked suite replay is a deliberate
requalification operation, not an implicit promotion gate for every change.

## 5. Negative evidence retained

The broad implementation diagnostics are not all green and are intentionally
not hidden:

| Broad diagnostic | Observed result |
|---|---:|
| PySHACL, all approved SHACL 1.0 Core tests | 97/98 pass |
| jsonld.js, JSON-LD 1.1 expand/compact | 618/631 pass |
| jsonld.js, all JSON-LD 1.1 FromRDF | 47/54 pass |
| RDFLib, broad SPARQL 1.1 read-only attempt | 196/241 pass |

Production qualification narrows the independent engine to the exact options
and standards components used by the adapter, and counts every non-attempted
vector as an exclusion. The suite receipts bind HSWM implementation bytes but
do not claim to execute those adapters; local integration tests cover that
separate edge. A broad failure retires or avoids that exact unsupported
surface; downstream scale cannot convert it into a success.

## 6. Remaining gates

- The Trace Context carrier needs a real remote boundary and end-to-end
  propagation test before it can be called integrated.
- OpenTelemetry 1.60.0 is observation metadata; no SDK has been selected.
- The existing bounded FastMCP viewer is not claimed as qualification against
  MCP revision 2026-07-28 or the TypeScript SDK 2.0.0. Those pins remain
  adoption metadata until a concrete implementation needs them.
- ISO GQL, SQL/PGQ, and GraphBLAS stay metadata-only. No lossless mapping from
  HSWM's typed n-ary atoms has been established.
- RDF 1.2, SHACL 1.2, and SPARQL 1.2 remain non-promoting draft lanes.

Accordingly, the precise answer is: the stable graph interoperability stack is
implemented and executable for the bounded canonical projection, but universal
whole-repository graph conversion and every remote/backend integration are not
claimed complete.
