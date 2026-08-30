# HSWM opaque-action identifiability pilot freeze

This preregistration authorizes one exploratory G0 instrument-identifiability
occurrence. It does not authorize a G1 efficacy claim or gate promotion. The
pilot asks whether the existing local outcome-to-credit-to-admission path can
produce a state-mediated behavioral contrast after the value leakage found in
the preceding G1-shaped micro occurrence is removed.

The canonical JSON SHA-256 of `protocol.v1.json` is
`b476af32e231afd5693ead80302a9a8326cd8a5652a07133edd4ed341a334007`.

Eight precommitted episodes use evaluator-bound opaque action codes. Each
episode makes, in order, one pre-outcome trajectory call, two revision-proposal
calls, and five fresh-behavior probes. Every completion has one tokenizer
preflight, so the fixed ceiling is 64 completion POSTs, 64 tokenizer POSTs, and
128 loopback HTTP POSTs. There is no retry, replacement, refill, resume,
adaptation, partial-look decision, or second occurrence.

The branches are ACTIVE, FORCED_OPPOSITE_FEEDBACK, NO_UPDATE, REMOVE, and
RESTORE. FORCED_OPPOSITE_FEEDBACK is an outcome-dependent counterfactual
control admitted under an explicit experimental policy. It is not the
outcome-independent sham required by a later complete G1 experiment.

The evaluator reveal remains outside the repository until the run. Its eight
entry commitments and ordered root are public in the protocol. The reveal is
bound to the final protocol digest before execution, validated before the
one-shot registry claim, withheld from every model request, and copied into the
result only after all scheduled behavior calls are sealed.

Pairwise equal standalone action-code token counts reduce one length cue. They
do not establish semantic opacity or exchangeability. Candidate-position
counterbalancing, raw-request leakage scans, normalized stateful-request
equivalence, and position-stratified no-state observations remain separate
checks.

A positive terminal requires ACTIVE and RESTORE correctness in all eight
episodes, FORCED_OPPOSITE_FEEDBACK correctness in none, both no-state branches
at or below their preregistered ceilings, the preregistered state contrast,
eight credited admissions in both stateful learning branches, and eight exact
REMOVE/RESTORE transitions. Any other structurally complete result is a
non-separation observation. Neither terminal is evidence of HSWM learning
efficacy: the evaluator is same-process, the compiled disposition exposes an
action code directly, arm order is fixed, and service-level independence is not
established.

Run the zero-call DGX preflight through the maintainer wrapper first:

```sh
~/bin/hswm-run exec HSWM_G1_OPAQUE_PREFLIGHT_RUN_ID --profile hswm \
  --cwd . -- uv run --locked python -m hswm.experiments.g1_micro_dgx \
  --protocol _research/causal_composition/preregistrations/g1_opaque_identifiability_pilot_2026-08-30/protocol.v1.json \
  --model-snapshot MODEL_SNAPSHOT \
  --lock-path /mnt/hswm/evidence/hswm-g1-micro-dgx.lock \
  --execution-registry /mnt/hswm/evidence/hswm-g1-opaque-identifiability-pilot-2026-08-30-consumption-v1 \
  --evaluator-reveal EXTERNAL_EVALUATOR_REVEAL \
  --preflight-only
```

Only after source freeze and independent audit may the same command be issued
once without `--preflight-only`, using a new wrapper run ID. Verify the frozen
protocol, one-shot seal, retained journals and state databases, runtime
identity, final request count, teardown, and shared-service restoration with:

```sh
uv run --locked python scripts/verify_hswm_g1_micro_bundle.py RESULT_JSON \
  --protocol _research/causal_composition/preregistrations/g1_opaque_identifiability_pilot_2026-08-30/protocol.v1.json \
  --execution-registry /mnt/hswm/evidence/hswm-g1-opaque-identifiability-pilot-2026-08-30-consumption-v1 \
  --dgx-runtime-receipt DGX_RUNTIME_RECEIPT
```

The local permit and state are experiment-only. They are not Atom v2 permits,
repository-canonical HSWM admissions, HSWM cognition, or evidence for
consciousness, selfhood, recursive HSWM-of-HSWMs composition, or scale-invariant
causal closure.
