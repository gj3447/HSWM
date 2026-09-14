# LLM semantic graph construction and formal evidence

This record accompanies the [implementation and research note](../../docs/research/HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.md).
It binds an existing canonical graph runtime to LLM semantic execution and
outcome-conditioned relation revision. It does not replace the CR/FCL target
with this bounded implementation.

The [Lean audit](lean-verification.v1.json) checks the exact bytes of two modules,
including the dependency axioms of every named theorem:

```sh
cd formal
lake env lean --trust=0 HSWMLLMSemanticGraph.lean
lake env lean --trust=0 HSWMSemanticEvidence.lean
```

`HSWMLLMSemanticGraph` has 24 named theorems. One tagged interpreter consumes
pre-outcome execution input and later outcome-conditioned revision input.
An explicit outcome-sensitive interpreter yields distinct successor text for
distinct observation text. This is a dataflow construction, not a proof of
semantic correctness or held-out improvement. Its fixed source/recipient/context
positions plus ordered extra roles abstract the runtime's schema-defined role
references; there is no proved TypeScript refinement.

`HSWMSemanticEvidence` has 10 named theorems over generic candidate and evidence
types, plus finite examples. The Nat mass update is optional candidate-evaluation
theory, not the runtime's semantic learner or a normalized Bayesian posterior.
The equal-marginals/different-joint-XOR counterexample preserves a limitation
that recursive composition must address.

Lean 4.32.1 and its bundled Std are reused. The audit permits only Lean's reported
foundations (`propext`, `Classical.choice`, `Quot.sound`); it introduces no `sorry`,
declared axiom, `admit`, or `native_decide`.

The [runtime verification](verification.v1.json), [source map](source-map.v1.json),
and [KG projection](../../ontology/development/HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.v1.json)
separate implementation checks from remaining research obligations. Raw local
development episodes and transport traces are not public research data.

The configured live provider was unavailable during this work, so actual model
calls are **0**. Injected transport results test wiring and persistence only.
