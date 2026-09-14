# Semantic graph implementation: proofs and remaining obligations

The [snapshot](../../development/HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.v1.json)
contains 48 owned nodes, 22 source-bound anchors and 137 typed relations.
It connects the user direction, implementation, primary research summaries,
34 Lean theorem statements and the original CR/FCL requirements.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source semantic=ontology/development/HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source semantic=ontology/development/HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.v1.json --profile v2 --query ontology/queries/hswm_llm_semantic_graph_2026-09-14/proofs_and_remaining.rq
```

The query returns 58 theorem-to-obligation rows; a theorem may support more
than one scoped construction. Every remaining requirement has status
`OPEN_NOT_DISCHARGED`. Structural support is not a discharge of that obligation.
All eight CR and eight FCL references remain in the graph; they are not all
covered by the new theorems. Original owner snapshots and their scientific
statuses are retained.

This is a checked-in projection, not a live KG write or an HSWM cognition path.
See the [implementation note](../../../docs/research/HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.md)
and [source map](../../../_research/llm_semantic_graph_v1/source-map.v1.json).
