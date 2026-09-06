# B0 successor — completed exploratory calibration

The separately frozen B0 successor completed all 12 episodes: train 0/8 and
descriptive `valid_seen` 0/4, with zero invalid episodes. Its predeclared
headroom classification is `FLOOR_OR_INSTRUMENT_REPAIR`. This is a valid
completed calibration at the observed floor; it supplies no efficacy,
G0/G1, or canonical HSWM admission claim.

The [protocol](../_research/causal_composition/preregistrations/alfworld_b0_successor_2026-09-06/protocol.v2.json)
and [selection](../manifests/HSWM_ALFWORLD_B0_SUCCESSOR_SELECTION_2026-09-06.json)
were committed before this occurrence. The consumed
[2026-08-30 B0](HSWM_ALFWORLD_B0_CALIBRATION_RESULTS_2026-08-30.md) remains
inconclusive and has no performance denominator; this successor neither
retries nor rewrites that record.

The wrapper's [original public receipt](raw/hswm_alfworld_b0_successor_2026-09-06/b0.public.json)
omits nested calibration aggregates. A separately identified
[posthoc public projection](raw/hswm_alfworld_b0_successor_2026-09-06/posthoc.public.json)
was replayed against the preserved private archive at its exact source
commit. It adds no environment/model call, task outcome, or resumed episode.
The archive hash, private/public binding, terminal evidence, and resource
totals are bound by the [evidence receipt](../evidence/EVIDENCE_HSWM_ALFWORLD_B0_SUCCESSOR_2026-09-06.json).

Observed totals: 240 environment actions and validated model responses;
240 tokenize and 240 completion requests (480 HTTP); 179468 input and 4265
output tokens. There is no reflection or cross-episode learning state.
The [S-5 comparison](HSWM_S5_B0_B2_COMPARISON_2026-09-06.md) reports the
separately selected B2 occurrence with its own costs and limits.
