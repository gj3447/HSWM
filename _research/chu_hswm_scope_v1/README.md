# CHU / HSWM scope validator

This is a read-only validation harness for the CHU umbrella and HSWM
LLM-function profile declaration. It verifies that CHU includes both the HSWM
and illustrative non-LLM world-model profiles, while only HSWM requires the
declared local LLM kernel. A shared world-model target records scope overlap;
it does not claim efficacy.

Run from the repository root after building the existing runtime:

```sh
npm --prefix src/hswm/effect-runtime run build
node _research/chu_hswm_scope_v1/verify.mjs
```

The compact JSON result reports the bound bundle digest and counts, recomputed
artifact and node-source bindings, generic/local SHACL results, query row
counts, and three rejected in-memory negative cases. It performs no runtime
execution, canonical write, model call, or live-KG publication.

The local shape checks declared role and containment contracts. The query
directory provides the separate scope, computational-contract, and
literature/gap readbacks. Passing validation establishes only source-bound
RDF structure and declared boundaries, not universal computation, a simulator
integration, world-model quality, or HSWM learning efficacy.
