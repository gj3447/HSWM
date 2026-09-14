# Literature-motivated semantic graph performance proofs

Read the [research note](../../docs/research/HSWM_LITERATURE_TO_PERFORMANCE_PROOF_2026-09-14.md)
for the exact assumptions, empirical source settings, counterexamples and remaining obligations.

Run from the repository root:

```sh
python3 _research/semantic_performance_proof_v1/verify_lean.py
```

The verifier uses the existing pinned Lean 4.32.1 and Std. It checks the compiler
binary hash, rebuilds the two prior definition/representation dependencies and
three new modules in a fresh temporary import directory, then checks each new
exact source with `--trust=0` and `#print axioms` for every public named theorem.
The [verification record](lean-verification.v1.json) includes exact source hashes,
the public theorem inventory, private helper counts and their transitive axioms.
Only `propext`, `Quot.sound`, and `Classical.choice` are permitted. No new package,
Mathlib, model, empirical premise axiom or native-evaluation axiom is introduced.
The default Lake targets do not include these standalone modules; the explicit
verifier is the reproducible check. Temporary compiled files are removed afterward.

`HSWMLocalEnsembleGain` enumerates the eight Boolean product-law outcomes and
proves strict majority gain for `good > bad > 0`. The perfectly correlated
countermodel has the same normalized single-voter marginal but no majority gain.
`HSWMOutcomeLearningGain` proves at most `N - 1` pre-update mistakes in a finite
realizable hypothesis list. List duplicates count toward N. Inconsistent outcomes
can eliminate the truth. Neither theorem establishes real-world feedback validity.

`HSWMSemanticPerformanceBridge` retains complete role-bearing graph candidates,
constructs local operators through `SemanticWeight.fromLlm`, and uses one forward
map for both Step and outcome filtering. The computed candidate update changes
which pre-existing semantic relation is selected. A symbolic strict-gain theorem,
the exact 18/27 to 20/27 witness, all truthful first observations, and the same
learner's arbitrary-sequence mistake bound are kernel checked. It is a deliberately
bounded reference model with an initially present true candidate, not a proof of
pretrained LLM interpretation, topology discovery, optimal selection, universal
generalization, equal-cost superiority or complete HSWM realization.

The [source map](source-map.v1.json),
[KG](../../ontology/identity/hswm_core/HSWM_SEMANTIC_PERFORMANCE_PROOF_ONTOLOGY.v1.json),
and [queries](../../ontology/queries/hswm_semantic_performance_proof_2026-09-14/README.md)
keep empirical findings, mathematical assumptions, proof scopes, transfer
obligations and negative evidence distinct. Existing CR/FCL judgments and
historical research records remain in force; no actual model was run here.
