# HSWM adversarial remediation design witnesses

Companion to the [remediation plan](../../docs/research/HSWM_ADVERSARIAL_REMEDIATION_PLAN_2026-09-27.md).
No model calls, canonical writes, hidden reasoning claims, or learned improvement.

Run from the repository root with the existing Node environment:

```sh
node _research/hswm_adversarial_remediation_v1/counterexamples.mjs
```

The script imports the existing 128-case finite W1 domain and checks that copying
two input fields matches 256 named E2 fields. It does not check base/final accuracy
or claim complete E2 passage. Independent literal tables for two authored laws
then expose relation sensitivity (4/8), role-value sensitivity (4/8 per law), and
a law-blind deterministic ceiling (12/16 under the uniform declared population).
A two-state alias exposes a fixed-visible-input ceiling of 1/2. Reading the hidden
bit changes the information set; no active reader is implemented here.

The checked-in `verification.v1.json` captures stdout with script/domain SHA-256
and the actual Node version. This is finite design qualification, not an LLM
experiment or a new F1/R8 result. Do not overwrite it when changing the source;
record a successor version. The script itself performs no writes or networking.

The source-bound plan graph is a local descriptive projection. Its proposed work
items are `PLANNED_NOT_RUN`; the finite witness is `CHECKED_FINITE_DESIGN_ONLY`.
It is not runtime state, live publication, authority admission, or causal learning.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source remediation=ontology/development/HSWM_ADVERSARIAL_REMEDIATION_2026-09-27.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source remediation=ontology/development/HSWM_ADVERSARIAL_REMEDIATION_2026-09-27.v1.json --profile v2 --query _research/hswm_adversarial_remediation_v1/queries/attack-remedy.rq
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source remediation=ontology/development/HSWM_ADVERSARIAL_REMEDIATION_2026-09-27.v1.json --profile v2 --query _research/hswm_adversarial_remediation_v1/queries/unaddressed-attacks.rq
```

Expected query results: seven attack/remedy pairs; zero attacks without a planned
remedy. Zero missing links means design coverage, never that the attacks have
already been resolved. The existing RDF adapter and its explicit dataset view are
reused. Hash verification remains a separate host check from SHACL conformance.

2026-09-27 validation: witness replay matched the saved output; all 18 artifact
bindings and local documentation links resolved; the bundle passed the existing
SHACL Core profile. The two queries returned seven planned-remedy pairs and no
unaddressed attack links. Manual endpoint review corrected the local-read attack
to R3 and the no-op/evidence attack to R2; structural coverage alone did not catch
that distinction. The selected ontology development route passed 49 existing
checks. These checks do not execute any proposed remediation or evaluate a model.
