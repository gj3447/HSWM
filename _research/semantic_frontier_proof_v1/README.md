# Semantic frontier proofs

The [report](../../docs/research/HSWM_SEMANTIC_FRONTIER_PROOFS_2026-09-14.md)
explains the five bounded extensions and their integrated reference construction.

```sh
python3 _research/semantic_frontier_proof_v1/verify_lean.py
```

This verifier reuses pinned Lean 4.32.1/Std, checks the compiler hash, builds four
prior modules and five new modules in a fresh temporary import directory, and
runs `--trust=0` plus `#print axioms` for every new public named theorem. Only
`propext`, `Quot.sound`, `Classical.choice` are allowed. Private helpers are covered
by transitive axiom checks. The default Lake targets exclude these standalone
modules, so use this explicit command. No new package or model is installed.

The [Lean audit](lean-verification.v1.json) records exact theorem names and source
hashes. The [source map](source-map.v1.json),
[KG](../../ontology/identity/hswm_core/HSWM_SEMANTIC_FRONTIER_PROOF_ONTOLOGY.v1.json),
and [queries](../../ontology/queries/hswm_semantic_frontier_proof_2026-09-14/README.md)
distinguish model assumptions, concrete computations, counterexamples and open
real-LLM transfer obligations. The [graph audit](graph-validation.v1.json) checks
these bindings using existing RDF 1.1, SHACL and SPARQL tools; this is not live KG
cognition or an efficacy judgment.

The synthesis grammar has three variables and AND only. Four deliberately
separating synthesis labels are clean. The subsequent assessment is a weighted
whole-domain census that overlaps those inputs, with one unit of label corruption.
The normalized cost is a declared reward debit, not measured token/currency cost.
Recursive composition retains whole joint candidates and passive metadata; it
does not establish scalable local credit or uncertainty calibration. All whole-HSWM
CR/FCL obligations and prior failures retain their status. No real model was run.
