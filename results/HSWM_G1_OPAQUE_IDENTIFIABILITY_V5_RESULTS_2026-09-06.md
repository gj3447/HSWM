# HSWM opaque-action identifiability v5 (G0-local, corrected control clause) result — 2026-09-06

> **Terminal (sealed by the instrument):** `V3_COMPLETE_G0_LOCAL_IDENTIFIABILITY_OBSERVED_NO_EFFICACY_INFERENCE`
>
> **Claim ceiling:** `MEASUREMENT_READY_SINGLE_OWNER_UNDER_DECLARED_OPAQUE_TASK`
>
> **Status:** `G0_LOCAL_MEASUREMENT_READY_SINGLE_OWNER_CANDIDATE_OBSERVED / G0_EXTERNAL_DEFERRED / G0_NOT_PASSED / G1_NOT_EVALUATED / NO_EFFICACY_INFERENCE`
>
> **Closure plan:** third S-3 occurrence under D-1, using the v5 rule revision
> chosen under the user's delegated 2026-09-06 decision.  This is the first
> occurrence whose preregistered G0-local rule was met.

## 1. Result

One frozen thirty-two-episode occurrence (protocol `180f7e5f…1892e`) ran on the
DGX with the v3 instrument, v4's seed-independent stratum-balanced no-state
orders, and the v5 rule: stateful arms gated per stateful position stratum,
controls bounded pooled at chance-plus-margin, the no-state own-position
pattern reported.  All 320 completions and 320 tokenizer preflights completed
without retry or refill; registry `COMPLETED_NO_RERUN`.

| Arm | Correct / 32 | Wilson 95% | Stateful stratum, correct code first (16) | Stateful stratum, correct code second (16) |
|---|---|---|---|---|
| ACTIVE | 32 | [0.893, 1.000] | 16 | 16 |
| RESTORE | 32 | [0.893, 1.000] | 16 | 16 |
| FORCED_OPPOSITE_FEEDBACK | 0 | [0.000, 0.107] | 0 | 0 |
| OUTCOME_INDEPENDENT_SHAM | 16 | [0.336, 0.664] | — | — |
| NO_UPDATE | 16 | [0.336, 0.664] | — | — |
| REMOVE | 16 | [0.336, 0.664] | — | — |

No-state arms by their *own* candidate position (reported, not gated):
NO_UPDATE 16/16 first, 0/16 second; REMOVE 16/16 first, 0/16 second; SHAM
6/16 first, 10/16 second.  `delta_state` = 0.625 (threshold 0.5).  Six-branch
signature rate 8/32.  Credited admissions 32/32/32; Atom v2 local Permit
commits 96; exact remove/restore 32/32; evaluator feedback salt-verified
32/32 from a separate OS user; position balance 16/16; sham-bit balance 16/16.

Every clause of the frozen v5 rule holds: ACTIVE and RESTORE ≥ 30/32 pooled
and ≥ 15/16 in each stateful stratum; FORCED_OPPOSITE ≤ 2/32 and ≤ 1/16 per
stratum; SHAM, NO_UPDATE, REMOVE ≤ 21/32 each; `delta_state` ≥ 0.5; 32 exact
remove/restore; 32 credited admissions per stateful arm; 96 Permit commits;
16/16 balances; 32 verified feedback bits.

## 2. What was observed, exactly

Across the three occurrences of the day (v3, v4, v5: 96 episodes, 960
completions) the stateful arms were correct 96/96 (ACTIVE) and 96/96
(RESTORE) while the forced-opposite arm was correct 0/96 and the no-state arms
followed a strict first-candidate default (48/96 each, exactly the balance the
designs imposed).  Under the opaque-action task, a compiled disposition in the
local state therefore mediates the model's choice: the choice tracks the state
across balanced candidate positions, inverts with a forced-opposite
disposition, disappears when the state is removed, and returns byte-exactly
when it is restored, with the evaluator's feedback bits verified by salt after
the seal.  That is the G0-local criterion of D-1 (separate-process,
separate-OS-user evaluator; precommitted reveal read only after the seal;
randomized and stratified candidate position; outcome-independent sham arm;
sealed trajectory before outcome; exact remove/restore; all-run manifest),
mechanically present and, under the v5 rule, satisfied.

## 3. What the occurrence does not show

- **Not G0 passed.**  G0-local is the single-owner sub-gate proposed by D-1
  (ratified); G0-external (a named second party, independent replay,
  external notarization) is a deferred publication gate.  The ceiling is
  `MEASUREMENT_READY_SINGLE_OWNER`, exactly as preregistered.
- **Not G1.**  The task is a two-code opaque disposition; no held-out
  behaviour, no fresh-task gain, no reuse-first comparator, no G1 estimand
  (D-3, now ratified as option A: the `project.v1.json` pass_rule) was
  evaluated.
- **Not efficacy, learning, or canonical admission.**  The Permit commits are
  the local Atom v2 path; no canonical HSWM revision, no efficacy inference.
- **Rule provenance.**  The v5 rule was frozen after two sealed occurrences
  showed the v3/v4 control clause to be unsatisfiable for a control that
  behaves as a control.  The v3 and v4 terminals stand as sealed; the v5 rule
  was applied only to this fresh occurrence.  A reader who prefers the
  original clause should read this result as "the same pattern, now under a
  satisfiable control clause", not as a promotion of the earlier runs.

## 4. Frozen occurrence

| Field | Value |
|---|---|
| Protocol | `_research/causal_composition/preregistrations/g1_opaque_identifiability_v5_2026-09-06/protocol.v1.json` |
| Design | `generation.design_revision = "v5"`, independent stratum-balanced no-state orders, rule `IDENTIFIABILITY_RULE_V5` embedded in `analysis` |
| Source commit | `d3c2a9bd…` |
| Runtime | NVIDIA GB10 `GPU-ffed5bca…`, `vllm/vllm-openai@sha256:e4f88a83…6089`, `Qwen/Qwen3.6-35B-A3B-FP8@95a723d0…3d989`, loopback fresh container, fresh caches |
| Registry | `/mnt/hswm/evidence/hswm-g1-opaque-v5-2026-09-06-consumption-v1`, `COMPLETED_NO_RERUN` |
| Result bundle | `7cbbfe3d…` |
| Public artifacts | `results/raw/hswm_g1_opaque_identifiability_v5_2026-09-06/{public_redacted_projection,independent_verification}.json`, `evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V5_2026-09-06.json` |

The remaining execution digests (preflight and live wrapper receipts, private
archive, registry, runtime binding and final receipt records, seed commitment,
reveal commitment root) are in the projection.

## 5. Custody, verification, and boundaries

Custody is unchanged: OS-user separation with mechanical readability checks
(the actor could not read the reveal before the run nor the ledger after it);
the actor holds passwordless sudo, so this is not privilege separation.  The
checked-in replay reports
`VALID_V3_FROZEN_FILES_ONE_SHOT_SEAL_AND_DGX_FINAL_ATTESTATION_JOIN`, 320
successful generation requests, shared services restored after quiescence.
It is a local structural replay by the same owner, not an independently
owned adjudication.

Prompts, completions, salts, canaries, correct codes, Permit keys and ledgers
stay in the private content-addressed archive.  The fractal status is
unchanged: `SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`.  G0 is
`NOT_PASSED`; G1 is `NOT_EVALUATED`; the live KG was not mutated by the
occurrence.

## 6. Next

S-3 is complete as a run and, under v5, as an observed G0-local candidate.
The closure plan's next steps are S-5 (first B0 and B2 comparator result
files, secondary ceiling under D-3 option A) and S-6 (burden cap and the
second-party question for G0-external).  The v1 done-state (D-4) still needs
a run in which outcome, credit, durable canonical revision through the real
Permit path, and changed held-out behaviour are all checked in; this
occurrence supplies the credit-to-Permit-to-state-readout segment only.
