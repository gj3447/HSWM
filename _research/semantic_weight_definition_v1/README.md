# Semantic Weight definition and hypergraph representation proofs

Read the [theory report](../../docs/research/HSWM_SEMANTIC_WEIGHT_DEFINITION_AND_HYPERGRAPH_2026-09-14.md)
for definitions, exact quantifiers, counterexamples and remaining HSWM obligations.
These two standalone Lean sources reuse the existing pinned Lean 4.32.1 and Std.

```sh
cd formal
lake env lean --trust=0 HSWMSemanticWeightDefinition.lean
lake env lean --trust=0 HSWMHypergraphRepresentation.lean
```

The existing default `lake build` targets do not include these standalone sources.
The explicit commands above check them. For the axiom audit, feed each exact source
followed by `#print axioms <fully qualified theorem>` for every named theorem to
`lake env lean --trust=0 --stdin`. The [verification record](lean-verification.v1.json)
binds source hashes, all theorem names, exact compiler identity and reported axioms.
Only Lean foundations `propext`, `Classical.choice`, `Quot.sound` are allowed;
`sorryAx`, native-evaluation axioms and declared goal axioms are rejected.

`SemanticWeight` declares an input-dependent local read and a role/context-conditioned
disposition. Its output `Law` remains a parameter, not a proved probability measure.
`fromLlm` constructs that disposition from a given encoder/operator; it does not
prove a real pretrained LLM correct. The independent-target read collision and
next-behavior Learn counterexamples have satisfiable, concrete witnesses.

`decode_encodeNary` reconstructs arbitrary finite per-factor arity, payload and
tagged incidence slots. Factor and slot addresses are finite indices; persistence
of external UIDs across migrations is not proved. The pair projection theorem
forgets all but observed-pair existence. The additive-potential theorem uses only
unary and binary Int-valued functions on three original Boolean variables.
`cubic_has_binary_composition` explicitly admits richer binary computations.

The [source map](source-map.v1.json) and [KG](../../ontology/identity/hswm_core/HSWM_SEMANTIC_WEIGHT_DEFINITION_ONTOLOGY.v1.json)
connect definitions, all checked theorems, scope assumptions and existing CR/FCL
obligations. The [KG queries](../../ontology/queries/hswm_semantic_weight_definition_2026-09-14/README.md)
use existing RDF 1.1 / SHACL / SPARQL tooling. This is operational and elementary
representation formalization, not new empirical learning efficacy or a change to
historical HSWM result statuses. No runtime code, package or model was installed.
