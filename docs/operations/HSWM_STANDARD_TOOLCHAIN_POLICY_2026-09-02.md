# HSWM standard-first graph toolchain policy

> **Status:** `OPERATIONAL_POLICY / SOURCE_LOCKED / ENGINEERING_QUALIFICATION_ONLY / SCIENTIFIC_NONCLAIM`
>
> **Date:** 2026-09-02
>
> **Target authority:** [HSWM Constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md)
>
> **Machine lock:** [HSWM graph standards acceptance v1](../../_research/graph_standards/HSWM_GRAPH_STANDARDS_ACCEPTANCE.v1.json)
>
> **Applied stack:** [HSWM full-stack graph engineering boundary](HSWM_FULL_STACK_GRAPH_ENGINEERING_2026-09-02.md)
>
> **Scope:** External graph standards, SDKs, conformance suites, MCPs, Skills, package provenance, and thin adapters

## 1. Answer first

HSWM now has one fail-closed, standard-first external-tooling path:

1. current official specification status is checked before selection;
2. a published standard and its official suite are preferred over a local profile;
3. an official SDK is preferred when one exists;
4. an independent implementation is identified as such and may be accepted only
   at an exact version, source commit, package integrity, license, and lockfile;
5. draft standards run only in a non-promoting experimental lane;
6. an HSWM adapter remains thin, bounded, and unable to claim canonical write,
   Permit, outcome truth, causal credit, learning, or efficacy.

This policy changes no canonical HSWM schema or atom state. It strengthens the
living-harness readout and engineering evidence instruments used to inspect
external projections. A standard test pass is not HSWM progress by itself.

## 2. Constitutional fit

| Constitution section 9 question | Answer |
|---|---|
| What canonical contract changes? | None. The lock is a research/tooling input manifest, not a `σ` migration or canonical atom admission. |
| Which HSWM role advances? | The readable living-harness projection and falsifiable engineering instrumentation. It does not instantiate cognition or learning. |
| What is claimed? | Exact source and package binding plus the narrow official-suite results below. No causal or efficacy claim is made. |
| Does it strengthen a real contract? | Yes. It makes source, license, suite tree, adapter package, runtime, counts, and claim ceiling machine-checkable and refuses silent promotion. |

## 3. Current official baseline

At the 2026-09-02 observation cut, the production lane uses stable, published
specifications. Newer drafts are tracked without letting them redefine a
success result; their status must be rechecked at the next adoption decision.

| Area | Stable lane | Current experimental or metadata lane | HSWM use |
|---|---|---|---|
| RDF dataset and bytes | [RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/) and [N-Quads 1.1](https://www.w3.org/TR/n-quads/), W3C Recommendations | [RDF 1.2 Concepts](https://www.w3.org/TR/rdf12-concepts/) is on the Candidate Recommendation track; [RDF 1.2 N-Quads](https://www.w3.org/TR/2026/WD-rdf12-n-quads-20260723/) was a 2026-07-23 Working Draft | RDF 1.1 remains the read-only exchange baseline; RDF 1.2 is experimental. |
| Dataset canonicalization | [RDFC-1.0](https://www.w3.org/TR/rdf-canon/), W3C Recommendation 2024-05-21 | No HSWM-local replacement algorithm | External canonicalization only; it does not define signatures or HSWM native identity. |
| Shapes | [SHACL 1.0](https://www.w3.org/TR/shacl/), W3C Recommendation 2017-07-20 | [SHACL 1.2 Core](https://www.w3.org/TR/shacl12-core/) remains a 2026 draft | Exported-graph structure only, never semantic truth or Permit. |
| JSON exchange | [JSON-LD 1.1](https://www.w3.org/TR/json-ld11/), W3C Recommendation 2020-07-16 | No compacted JSON spelling becomes a signed native input | Human/API projection only. |
| Provenance | [PROV-O](https://www.w3.org/TR/prov-o/), W3C Recommendation 2013-04-30 | The checked-in HSWM mapping is deliberately limited to source entity → derivation activity → derived view entity | Asserted exchange lineage only, not provenance truth or causal identification. |
| Query | [SPARQL 1.1 Query](https://www.w3.org/TR/sparql11-query/) is the stable local RDF query baseline | SPARQL 1.2 documents are drafts; [ISO GQL](https://www.iso.org/standard/76120.html) and [SQL/PGQ](https://www.iso.org/standard/79473.html) are recorded by published edition and corrigendum but their copyrighted text is not vendored | Local read-only `SELECT`/`ASK`; updates, remote datasets, `SERVICE`, and write-back are refused. |
| Sparse graph compute | No W3C or ISO native-HSWM standard | [GraphBLAS C API 2.1.0](https://graphblas.org/docs/GraphBLAS_API_C_v2.1.0.pdf) is a stable project specification | A future sparse compiled view, not a lossless n-ary state or learning rule. |
| Distributed correlation | [W3C Trace Context](https://www.w3.org/TR/trace-context/), Recommendation 2021-11-23 | [OpenTelemetry specification 1.60.0](https://opentelemetry.io/docs/specs/otel/) is the observed project baseline | Correlation and observability only, not canonical provenance or causal credit. |

No listed standard defines HSWM Permit issuance, storage recovery truth,
independent outcome attribution, causal credit, macro-learning, or real-LLM
efficacy. Those remain project-local research obligations.

## 4. Authority and selection order

Use the first adequate level and stop:

1. published official standard;
2. official conformance or test suite at a fixed source commit and selected-tree digest;
3. official SDK at an exact release, source commit, and package or image integrity;
4. independently maintained implementation, clearly labelled non-authoritative,
   exact-locked and qualified against the official suite;
5. a thin HSWM adapter only for the remaining boundary.

Catalog presence, GitHub popularity, package naming, and a passing local smoke
do not change an artifact's authority class. An ISO standard identifier is
recorded without copying unlicensed standard text. W3C suite material is
materialized outside the repository and its recorded license bytes are checked.

## 5. Executed qualification cut

The suite commits, clean selected trees, archive digests, manifests, licenses,
npm/PyPI artifact integrities, complete package-lock and uv-lock digests,
qualification-runner and implementation-artifact digests, runtimes, exact
counts, exclusions, nonclaims, and content-addressed receipt digests are checked
by the machine lock. The official-suite runners call the selected independent
engines directly; implementation digests bind HSWM adapter bytes but do not
claim those adapter modules were imported by the suite runner. Their behavior
is covered separately by local integration tests. Node qualifications use a fresh temporary
`npm ci --ignore-scripts` installation with isolated config and cache. Python
qualifications use `uv run --isolated --locked`, an exact CPython 3.12.13 and uv
0.12.3, the exact `graph` extra from the dedicated
[`graph_standards/runtime`](../../_research/graph_standards/runtime/) project,
and disabled implicit Python downloads. This independent lock preserves the
historical root dependency lock byte-for-byte. Neither path trusts the
repository's existing installed packages.

The manual
[`graph-standards-requalification.yml`](../../.github/workflows/graph-standards-requalification.yml)
workflow repeats that full source fetch and six-profile replay under the exact
locked runtimes, then compares every result byte-for-byte with the checked-in
receipt. Ordinary CI verifies the lock and adapters without silently performing
a networked standards requalification.

| Profile | Observed result | Exact ceiling |
|---|---|---|
| RDF 1.1 N-Quads syntax with `n3@2.7.2` | `PASS`: 53 positive + 32 negative = 85 `rdft:Approved` vectors. Two manifest entries without `rdft:Approved` are excluded from the stable count. [Receipt](../../_research/graph_standards/results/RDF11_NQUADS_N3_2_7_2.v1.json) | The pinned parser matches those approved syntax fixtures; this is not universal parser or HSWM emitter conformance. |
| RDF 1.2 N-Quads delta syntax with `n3@2.7.2` | `PASS`: 7 positive + 20 negative = 27 current delta fixtures. [Receipt](../../_research/graph_standards/results/RDF12_NQUADS_N3_2_7_2_EXPERIMENTAL.v1.json) | Draft-only diagnostic; it cannot promote the stable baseline. |
| RDFC-1.0 with `rdf-canonize@5.0.0` | `PASS`: 64 canonical-output + 21 identifier-map + 1 complexity rejection = 86 approved vectors. [Receipt](../../_research/graph_standards/results/RDFC10_RDF_CANONIZE_5_0_0.v1.json) | The pinned independent processor matches the tested RDFC aspects; it is not W3C itself and does not prove signatures, truth, or HSWM identity. |
| HSWM RDF projection through the qualified processor | The actual TypeScript fixture is a byte-identical fixed point of external `RDFC-1.0`. [Test](../../src/hswm/effect-runtime/test/canonical-atom-v2-rdf-projection.test.ts) | One current blank-node-free HSWM fixture and profile only; the local sorter is still not called an RDFC implementation. |
| SHACL 1.0 with `pyshacl==0.40.1` | `PASS`: 97/97 attempted approved Core fixtures; the one `sh:uniqueLang` fixture is explicitly excluded because that component is absent from the HSWM shape. [Receipt](../../_research/graph_standards/results/SHACL10_PYSHACL_HSWM_CORE.v1.json) | Used-component profile only. The checked-in shape validates structural projection constraints, not canonical admission or truth. |
| JSON-LD 1.1 with `jsonld@9.0.0` | `PASS`: 21/21 attempted official FromRDF fixtures under the exact HSWM options; 33 blank-node, direction, native-type, RDF-type, or processing-mode fixtures stay excluded. [Receipt](../../_research/graph_standards/results/JSONLD11_JSONLDJS_HSWM_FROMRDF.v1.json) | Source-bound blank-node-free FromRDF + local compaction view only, not universal JSON-LD conformance. |
| SPARQL read-only view with `rdflib==7.6.0` | `PASS`: 40/40 attempted official basic/triple-match/graph/ASK fixtures; all other suite entries remain exclusions. [Receipt](../../_research/graph_standards/results/SPARQL11_RDFLIB_HSWM_BASIC.v1.json) | Backward-compatible local `SELECT`/`ASK` subset only; no protocol, update, federation, entailment, `CONSTRUCT`, or `DESCRIBE`. |

The RDFC Recommendation itself warns that passing every suite case checks only
the aspects represented by those cases, not complete universal conformance.
The receipts preserve the same ceiling.

Broader diagnostic runs remain visible and failed: PySHACL Core `97/98`,
JSON-LD expand/compact `618/631`, JSON-LD FromRDF `47/54`, and broad SPARQL
`196/241`. These failures are not relabelled as production passes. The narrower
production profiles correspond to the independent-engine surface used by the
HSWM adapters and retain every exclusion in the machine lock; they are not
end-to-end official-suite executions through the HSWM wrapper. PROV-O has a constrained mapping without
an executable official suite. Trace Context has a strict carrier but is not yet
wired to a real remote runtime. GQL/SQL-PGQ, GraphBLAS, and OpenTelemetry remain
metadata or future adapter work.

## 6. MCP and Skill boundary

[OpenAI's MCP documentation](https://learn.chatgpt.com/docs/extend/mcp) describes
MCP as the connection to tools and context and supports local `stdio` and
Streamable HTTP servers. [OpenAI's Skills documentation](https://learn.chatgpt.com/docs/build-skills)
defines Skills as reusable instruction and resource packages. HSWM fixes the
following division:

- MCP: bounded live data, action, authentication, and authorization interface;
- Skill: reusable workflow, domain instructions, scripts, references, and assets;
- `AGENTS.md`: persistent repository-wide policy;
- canonical HSWM state: none of the above unless an independently valid
  canonical transition admits an atom under the current schema.

The observed final MCP protocol revision is
[2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28). A future
new TypeScript MCP implementation must begin with the official split SDK
`@modelcontextprotocol/{core,client,server}@2.0.0`, pinned to its release source
and three npm tarball integrities recorded in the machine lock. It has no
dependency lockfile and is not installed now because HSWM has no current
TypeScript MCP implementation requiring it; actual adoption must create one.

The existing Phoenix projection stays a bounded migration-review item: it uses
standard MCP transport but the independent FastMCP framework, a dedicated
VIEWER identity, four read-only tools, and no canonical write path. Replacing a
working security boundary merely to add a dependency is not an accepted use case.

The [official MCP Registry](https://registry.modelcontextprotocol.io/) is used
only to discover metadata. Its entry is never auto-installed or executed.
Publisher, repository and release, package or OCI digest, lockfile integrity,
license, auth scope, exact capability allowlist, and an isolated smoke are
required independently.

OpenAI system Skills are host-managed and used when their trigger matches.
OpenAI curated Skills may be installed only for a concrete task at an immutable
repository revision. At this observation cut there is no curated Lean, RDF,
SHACL, or graph-engineering Skill, so none was installed. The project-local
`hswm-research-readout` Skill was instead corrected to the current canonical
atom and schema-relative owner model and validated with the official Skill
validator.

## 7. Reproduction

Static lock, package, receipt, policy, and provenance validation:

```bash
uv run hswm-graph-standards verify
uv run --project _research/graph_standards/runtime --locked --extra graph \
  pytest -q tests/test_graph_standard_tooling.py \
  tests/test_standard_graph_view.py tests/test_trace_context.py
```

The CLI verifies a complete source closure. An installed wheel must supply
`--repository-root` for a full checkout or extracted sdist (and may supply
`--manifest` explicitly); the wheel alone is not reclassified as the separate
npm or research artifact.

Materialize a suite outside the repository, at only its locked commit:

```bash
uv run hswm-graph-standards fetch \
  --source-id w3c-rdf-tests-rdf11-nquads \
  --destination /tmp/hswm-w3c-rdf-tests
```

Run the stable N-Quads profile without changing its checked-in receipt:

```bash
uv run hswm-graph-standards qualify \
  --profile rdf11-nquads-n3 \
  --source-root /tmp/hswm-w3c-rdf-tests
```

The fetcher uses direct Git argv, credential-free HTTPS, no shell execution,
an exact commit, a clean selected git tree, a deterministic commit-bound
archive digest, manifest bytes, and license bytes. Qualification refuses local
tracked or untracked changes under that selected tree. The fetcher also refuses
an existing destination and refuses to vendor a suite inside the HSWM
repository.

## 8. Next bounded order

1. Wire the Trace Context carrier only at an actual remote HTTP boundary and
   qualify propagation end to end; do not store it as canonical provenance.
2. Select and qualify an OpenTelemetry SDK only for that concrete runtime.
3. Add GQL/SQL-PGQ or GraphBLAS only after a backend supplies an explicit
   mapping-loss, invalidation, no-write-back, and parity contract.
4. Re-evaluate RDF 1.2, SHACL 1.2, and SPARQL 1.2 after publication as stable
   Recommendations; current draft results cannot promote the stable lane.

These steps improve interoperability and falsifiability. They do not close the
separate TypeScript-to-Lean refinement, real storage recovery, independent
outcome and causal-credit, or revision-caused LLM-efficacy obligations.
