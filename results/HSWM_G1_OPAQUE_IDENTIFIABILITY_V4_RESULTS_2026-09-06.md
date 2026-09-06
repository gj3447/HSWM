# HSWM opaque-action identifiability v4 (G0-local, independent no-state orders) result — 2026-09-06

> **Terminal (sealed by the instrument):** `V3_COMPLETE_NO_SEPARATION_NO_EFFICACY_INFERENCE`
>
> **Claim ceiling:** `INSTRUMENT_VALIDATION_ONLY`
>
> **Status:** `G0_LOCAL_CANDIDATE_NOT_OBSERVED / G0_EXTERNAL_DEFERRED / G0_NOT_PASSED / G1_NOT_EVALUATED / NO_EFFICACY_INFERENCE`
>
> **Closure plan:** a second S-3 occurrence under D-1, using the v4 design
> revision chosen under the user's delegated 2026-09-06 decision.

## 1. Result

One frozen thirty-two-episode occurrence (protocol `052f5198…32017`) ran on the
DGX with the v3 instrument and rule and the v4 generative change: NO_UPDATE and
REMOVE candidate orders drawn from the seed independently of the stateful
order, balanced 8/8 within each stateful position stratum.  All 320
completions and 320 tokenizer preflights completed without retry or refill;
registry `COMPLETED_NO_RERUN`.

| Arm | Correct / 32 | Wilson 95% | Correct when the code is first in the arm's own order (16) | Correct when second (16) |
|---|---|---|---|---|
| ACTIVE | 32 | [0.893, 1.000] | 16 | 16 |
| RESTORE | 32 | [0.893, 1.000] | 16 | 16 |
| FORCED_OPPOSITE_FEEDBACK | 0 | [0.000, 0.107] | 0 | 0 |
| OUTCOME_INDEPENDENT_SHAM | 14 | [0.282, 0.607] | 7 | 7 |
| NO_UPDATE | 16 | [0.336, 0.664] | 16 | 0 |
| REMOVE | 16 | [0.336, 0.664] | 16 | 0 |

`delta_state` = 0.641 (threshold 0.5).  Six-branch signature rate 8/32.
Credited admissions 32/32/32; Atom v2 local Permit commits 96; exact
remove/restore 32/32; evaluator feedback salt-verified 32/32 from a separate
OS user; position balance 16/16.

**Why the rule fails again, and what that shows.**  The failing clause is the
same one as in v3: a no-state arm may be correct in at most 12 of the 16
episodes of each position stratum.  v4 removed the coupling between the
no-state orders and the stateful order, and the no-state arms still split
exactly 16/16 versus 0/16.  The stratum the rule uses is the arm's *own*
candidate position, and the no-state behaviour of this model is a strict
first-candidate default; such a default is correct in every episode where the
correct code happens to be first in the arm's own order and in none of the
others, whatever that order is.  The clause is therefore unsatisfiable by
construction for a control that behaves exactly as a control should (chance
overall, position-determined), while the stateful arms were 32/32 in both
strata of the stateful order.  This is a preregistration defect in the
control clause, not an ambiguity in the data; it was not visible in v2 (eight
episodes, coupled orders) and became legible only with balanced independent
orders.

The sealed terminal is binding for this occurrence (RG-4; SR-4).  The next
family, v5, replaces the control clause with per-stateful-stratum floors on
the stateful arms and pooled chance ceilings on the controls, before any
further occurrence.

## 2. Frozen occurrence

| Field | Value |
|---|---|
| Protocol | `_research/causal_composition/preregistrations/g1_opaque_identifiability_v4_2026-09-06/protocol.v1.json` |
| Design | `generation.design_revision = "v4"`, no-state order policy `INDEPENDENT_SEED_DERIVED_BALANCED_WITHIN_EACH_STATEFUL_POSITION_STRATUM` |
| Rule | identical to v3 (`hswm.experiments.g1_opaque_v3.IDENTIFIABILITY_RULE`) |
| Source commit | `231ee056…7ee7` |
| Runtime | NVIDIA GB10 `GPU-ffed5bca…`, `vllm/vllm-openai@sha256:e4f88a83…6089`, `Qwen/Qwen3.6-35B-A3B-FP8@95a723d0…3d989`, loopback fresh container |
| Registry | `/mnt/hswm/evidence/hswm-g1-opaque-v4-2026-09-06-consumption-v1`, `COMPLETED_NO_RERUN` |
| Result bundle | `11682e8b…9380f` |
| Public artifacts | `results/raw/hswm_g1_opaque_identifiability_v4_2026-09-06/{public_redacted_projection,independent_verification}.json`, `evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V4_2026-09-06.json` |

The execution digests (preflight and live wrapper receipts, private archive,
registry, runtime binding and final receipt records) are in the projection.

## 3. Custody, verification, and boundaries

Custody is unchanged from v3: OS-user separation with mechanical readability
checks; the actor holds passwordless sudo, so this is not privilege
separation; G0-external stays deferred.  The checked-in replay reports
`VALID_V3_FROZEN_FILES_ONE_SHOT_SEAL_AND_DGX_FINAL_ATTESTATION_JOIN` with 320
successful generation requests and shared services restored.

Prompts, completions, salts, canaries, correct codes, Permit keys and ledgers
stay in the private content-addressed archive.  The fractal status is
unchanged; G0 is `NOT_PASSED`; G1 is `NOT_EVALUATED`; no efficacy inference;
the live KG was not mutated by the occurrence.
