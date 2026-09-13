# Native engineering checkpoint — 2026-09-13

The user directed continued conversion of active HSWM-owned code to TypeScript,
Effect, and functional domain code. The exact instruction is preserved in
[`user-instruction.v1.json`](../../_research/native_migration_2026-09-13/user-instruction.v1.json).
This checkpoint records a bounded implementation change. **The full migration
remains incomplete.** The active-surface
[inventory](HSWM_NATIVE_MIGRATION_INVENTORY_2026-09-13.md) retains Python-backed
entrypoints and development checks as open work.

The conceptual change is in implementation language and effect boundaries.
HSWM's target remains one token-native macro-neural network with an evolving
hypergraph, recursively composable under FCL-1 through FCL-8. Repository
projections, CLIs, and passing tests are engineering instruments. This work
does not establish HSWM efficacy, causal credit, consciousness, or realization
of the target. Existing RED findings and success criteria remain binding.

## Completed bounded surfaces

| Surface | Native implementation and evidence |
| --- | --- |
| KG exchange | Pure bundle validation and deterministic RDF 1.1 N-Quads/PROV-O projection reproduce the two published September 13 bundles, including exact byte hashes and descriptors. Native local SPARQL reproduces every result cell of all 12 saved queries. |
| Knowledge catalogs | Fixed Git content, curator inputs, support-source pins, complete catalogs, bundles, and Markdown indexes reproduce both published maps. The CLI checks every input hash and writes only into a new output directory. |
| Conditional task | Native synthesis, preview, probe, and authored replay preserve the complete historical demo output and a source-bound 36-case behavior/refusal corpus. Integer, floating-point, boolean, and large-integer input distinctions survive decoding and provenance hashes. Ten numerical oracle cases match exact output bytes. |
| USL | Native v1/v2 projection and project/preview CLI tests include a complete v2 Python-reference golden. v1 preserves decimal provenance digests; v2 retains its explicit wire restrictions. This remains a bounded projection, not cognition, routing, or learning. |

The task domain also validates `not`/`any` branches, AST depth and total-node
bounds, all supplied observations and outcomes, access, nonnegative costs,
early exit/conflict conditions, exact relation references, and continuation
bindings. Synthesis enumerates candidates lazily within the original grammar.
These checks repaired omissions in the initial port before activation.

`NativeTaskIo`, `PosixFileSystem`, and `BoundedSubprocess` isolate effects from
pure domain functions. The functional AST check now covers the added native,
catalog, and general-JSON modules. No Python subprocess implements the new
task, USL, KG, or catalog commands.

## Standard qualification and limits

The selected RDF engines are independent implementations, not W3C SDKs. Exact
versions, source commits, licenses, package integrities, and the dependency
lock are recorded in
[`source-pins.v1.json`](../../_research/graph_standards/native_typescript_2026-09-13/source-pins.v1.json).

The pinned official W3C SHACL Core suite selected 98 approved tests and passed
all 98 with no exclusions. Report comparison follows the suite's prescribed
normalization and then compares RDFC-1.0 canonical graphs. The
[lineage record](../../_research/graph_standards/native_typescript_2026-09-13/qualification/lineage.json)
preserves two earlier failed harness attempts: incorrect comparison of optional
details/path structures, and exhaustion of the canonicalizer's default work
budget. The final comparison uses an explicit finite work budget and timeout.
No expected result or selected test was removed.

The official SPARQL conformance suite has **not** yet been run against this
adapter. The 12 saved-query goldens establish the HSWM query surface only.
Remote queries, updates, SHACL-SPARQL/JS/rules, and imports are refused by the
local bounded adapter. RDF 1.2/draft functionality is not promoted. The existing
finite-number and safe-integer KG wire profile remains explicit; the task CLI
has its separate Python-compatible numeric representation.

The vendor constructors are loaded through a thin checked runtime interface
because upstream declaration closures conflict with this repository's strict
TypeScript settings. Global type checking was not weakened. Existing locked
dependency versions did not change; the new engines add their pinned closure.

## Use and remaining work

An isolated checkout containing only this core checkpoint passed the complete
runtime suite: **1,017 tests passed; 10 existing external-integration tests
skipped** across 146 test files. Strict checking, the normal build, the DNRD
build, and package dry-run also passed. A subsequent lint-only change rejects
TypeScript suppression directives; its four focused tests and strict check
passed. The [verification receipt](../../_research/native_migration_2026-09-13/verification.v1.json)
binds these observations to source bytes and records the isolated setup failures
that were resolved before the clean run. Test success is engineering evidence.

The separate [engineering KG bundle](../../ontology/development/HSWM_NATIVE_ENGINEERING_CHECKPOINT_2026-09-13.v1.json)
connects the verbatim user request, implementation sources, verification,
preserved failures, and remaining migration surfaces. Its checked-in RDF/PROV
projection and saved queries are derived artifacts; no live KG publication is
claimed by this checkpoint.

Build with `npm --prefix src/hswm/effect-runtime run build`, using the locked
Node/npm toolchain. Checkout launchers are:

```text
src/hswm/effect-runtime/bin/hswm-task
src/hswm/effect-runtime/bin/hswm-usl
src/hswm/effect-runtime/bin/hswm-kg-bundle
src/hswm/effect-runtime/bin/hswm-knowledge-catalog
```

Historical artifacts and published KG UIDs are not overwritten. Native
reproduction retains the historical source pins; new engineering observations
receive a separate snapshot identity. Python compatibility commands and the
v3 `hswm-dev` USL/ontology/docs pytest routes remain active until their full
contracts have native replacements. Occurrence completion, legacy replay,
research-fabric operations, efficacy verification, graph-standard operations,
publication, and maintenance tooling require their own completion checks.

The next development step is to finish those active surfaces, replace the
selected development routes without dropping coverage, and then resume the
outcome-bound research loop. Implementation migration alone cannot resolve any
upstream scientific failure.
