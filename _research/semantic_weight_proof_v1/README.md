# Semantic Weight constructive proof

Read the [proof report](../../docs/research/HSWM_SEMANTIC_WEIGHT_CONSTRUCTIVE_PROOF_2026-09-14.md)
for the exact model, derivations and unproved HSWM connections. These are standalone
formal artifacts using the repository's existing Lean 4.32.1 toolchain and Std.
No package or model download is needed.

From the checkout:

```bash
cd formal
mkdir -p .lake/build/lib/lean
lake env lean --trust=0 -o .lake/build/lib/lean/HSWMFiniteSemanticLearning.olean HSWMFiniteSemanticLearning.lean
lake env lean --trust=0 -o .lake/build/lib/lean/HSWMSemanticQuotient.olean HSWMSemanticQuotient.lean
lake env lean --trust=0 HSWMSemanticLearningLimits.lean
lake env lean --trust=0 HSWMFiniteSemanticRefinement.lean
```

The historical default targets in `formal/lakefile.toml` are unchanged. A default
`lake build` does not verify these four new modules. The commands above select
their exact source files. `--trust=0` uses the pinned Lean implementation to recheck
imports; this is not verification by a separate checker implementation.

For the dependency audit, pass each exact source followed by `#check` and
`#print axioms` for every named theorem to `lake env lean --trust=0 --stdin`.
Only the foundational `propext`, `Classical.choice`, and `Quot.sound` are allowed.
Check both the reported axiom set and the count of audited named declarations.
Do not accept `sorryAx`, native-evaluation axioms, or a new axiom asserting the goal.
The [verification record](verification.v1.json) binds source bytes, theorem names,
compiler identity, results and scope. Raw session output stays local.

The positive learner requires eight exhaustive, noiseless, resettable responses
for three already named Boolean roles. Its future-input correctness is not
unseen-domain generalization. Its polynomial support is not open-ended variable
discovery. The quotient concerns the execution read view, not permission or
canonical lineage deletion. The missing-input theorem excludes exact recovery
from a fixed incomplete transcript; it is not a general adaptive lower bound.

Existing FCL/CR statuses, experimental RED findings and runtime behavior remain
unchanged. New empirical model efficacy, causal custody and whole-HSWM realization
are not outputs of this proof program.

The source-bound [proof graph](../../ontology/identity/hswm_core/HSWM_SEMANTIC_WEIGHT_CONSTRUCTIVE_PROOF_ONTOLOGY.v1.json)
uses the existing native RDF 1.1 / SHACL 1.0 / PROV-O projection. With the pinned
Node 24.13.0 available, run from the checkout:

```bash
src/hswm/effect-runtime/bin/hswm-kg-bundle validate \
  --source proof=ontology/identity/hswm_core/HSWM_SEMANTIC_WEIGHT_CONSTRUCTIVE_PROOF_ONTOLOGY.v1.json \
  --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query \
  --source proof=ontology/identity/hswm_core/HSWM_SEMANTIC_WEIGHT_CONSTRUCTIVE_PROOF_ONTOLOGY.v1.json \
  --profile v2 \
  --query ontology/queries/hswm_semantic_weight_proof_2026-09-14/theorems_and_open_obligations.rq
```

SHACL checks the positive structural profile, not mathematical truth. The
[graph validation record](graph-validation.v1.json) binds projection results,
cross-source references and coverage without a recursive source-hash cycle.
