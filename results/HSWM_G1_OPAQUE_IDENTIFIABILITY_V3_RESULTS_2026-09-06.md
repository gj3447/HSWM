# HSWM opaque-action identifiability v3 (G0-local) result — 2026-09-06

> **Terminal (sealed by the instrument):** `V3_COMPLETE_NO_SEPARATION_NO_EFFICACY_INFERENCE`
>
> **Claim ceiling:** `INSTRUMENT_VALIDATION_ONLY`
>
> **Status:** `G0_LOCAL_CANDIDATE_NOT_OBSERVED / G0_EXTERNAL_DEFERRED / G0_NOT_PASSED / G1_NOT_EVALUATED / NO_EFFICACY_INFERENCE`
>
> **Closure plan:** step S-3 executed under the ratified decision D-1; the
> first attempt of the day was VOID and the repaired rerun followed SR-3.

## 1. Result

One frozen thirty-two-episode occurrence ran on the DGX against the pinned
`Qwen/Qwen3.6-35B-A3B-FP8` revision `95a723d0…3d989` in the pinned vLLM image,
with the evaluator in a separate OS user, balanced candidate positions, an
outcome-independent sham arm, and every credited admission crossing the built
Atom v2 local Permit commit process.  All 320 completions and 320 tokenizer
preflights completed without retry or refill; the one-shot registry sealed
`COMPLETED_NO_RERUN`.

| Arm | Correct / 32 | Wilson 95% | Correct in position-1 stratum (16) | Correct in position-2 stratum (16) |
|---|---|---|---|---|
| ACTIVE | 32 | [0.893, 1.000] | 16 | 16 |
| RESTORE | 32 | [0.893, 1.000] | 16 | 16 |
| FORCED_OPPOSITE_FEEDBACK | 0 | [0.000, 0.107] | 0 | 0 |
| OUTCOME_INDEPENDENT_SHAM | 20 | [0.453, 0.771] | 11 | 9 |
| NO_UPDATE | 16 | [0.336, 0.664] | 16 | 0 |
| REMOVE | 16 | [0.336, 0.664] | 16 | 0 |

`delta_state` = 0.594 (threshold 0.5).  Six-branch signature rate 0/32.
Credited admissions: ACTIVE 32, FORCED_OPPOSITE 32, SHAM 32.  Atom v2 local
Permit commits 96 (3 per episode).  Exact remove/restore transitions 32/32.
Evaluator feedback bits salt-verified 32/32; evaluator reported a separate OS
uid in 32/32 episodes.  Correct-position balance 16/16; sham-bit balance
16/16.

**Why the preregistered rule fails.**  Every clause of the frozen
identifiability rule holds except one: a no-state arm may be correct in at most
12 of the 16 episodes of each position stratum, and both NO_UPDATE and REMOVE
were correct in 16/16 of the position-1 stratum (and 0/16 of the position-2
stratum).  The no-state arms are a deterministic first-candidate heuristic,
which the balanced design turns into exactly 16/32.  The rule treats a stratum
in which the no-state arm is fully predictable as uninformative for the
stateful arms, so the occurrence is `NO_SEPARATION` under the rule as frozen.
The terminal is binding and is not reopened here (RG-4 no post-hoc
immunization; SR-4).

## 2. What the occurrence does and does not show

- **Shows (instrument validation):** the separate-process, separate-user
  evaluator with a precommitted reveal read only after the seal; balanced
  positions; an outcome-independent sham arm; thirty-two exact remove/restore
  transitions; ninety-six real local Permit commits; fresh-container runtime
  binding and final attestation; one-shot registry; all of it verified by the
  checked-in replay (`independent_verification.json`).  This is the first
  occurrence in which every G0-local criterion of D-1 was mechanically
  present.
- **Descriptive only (not a preregistered estimand):** within the position-2
  stratum the stateful arms were 16/16 correct against 0/16 for both no-state
  arms and 0/16 for the forced-opposite arm; the sham arm sat at 62.5%.  A
  future rule that contrasts arms within each stratum would be a new
  preregistration, not an amendment of this one.
- **Does not show:** G0-local `MEASUREMENT_READY_SINGLE_OWNER` (rule not met);
  G0-external (no second party); any G1 estimand; any HSWM learning or
  efficacy; canonical HSWM admission (the Permit commits are the local Atom v2
  path, not canonical authority); reuse-first comparator superiority.

## 3. Frozen occurrence

| Field | Value |
|---|---|
| Protocol | `_research/causal_composition/preregistrations/g1_opaque_identifiability_v3_2026-09-06-r2/protocol.v1.json` |
| Protocol canonical / file SHA-256 | `2363815e…96fc6` / `7dababcf…be7ab` |
| Seed commitment / reveal commitment root | `13298e83…f8162` / `f8fd4401…d308c` |
| Code selection | first seed-ordered candidate pair with equal offline token counts (pool `f5f3ddfe…7a99e`, counts `dc343f08…222be`, 32 candidates per episode) |
| Tokenizer binding | `MEASURED` inside the pinned image with Docker network `none` |
| Freeze | `FROZEN` on 2026-09-06, draft canonical `30941611…4661f` |
| Source commit / tree | `647fcdec…0ab47` / `00edfdd5…3ad002` |
| GPU | NVIDIA GB10 `GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5` |
| Image | `vllm/vllm-openai@sha256:e4f88a83…6089` (id `30a38a1d…d95f`) |
| Endpoint | `http://127.0.0.1:18080`, loopback-bound fresh container, fresh caches |
| Preflight run | `hswm-g1-opaque-v3-r2-preflight-20260906`, receipt `e20cf472…02c0a` |
| Live run | `hswm-g1-opaque-v3-r2-occurrence-20260906`, wrapper receipt `495482c7…4d4cb`, private archive `5d822d09…1af3f36` (15,134,720 bytes) |
| Registry | `/mnt/hswm/evidence/hswm-g1-opaque-v3-2026-09-06-r2-consumption-v1`, `c81f02f2…e264d`, `COMPLETED_NO_RERUN` |
| Result bundle | `69d8d784…44584` |
| Runtime binding / final receipt records | `9d922f23…9fc266` / `d8b35954…348fce` |

## 4. The VOID attempt and the SR-3 rerun

The first occurrence of the day (`hswm-g1-opaque-v3-occurrence-20260906-r2`,
protocol `g1_opaque_identifiability_v3_2026-09-06`, canonical `4d049c7b…4e6d`)
completed all 320 calls, wrote the seal marker, received the reveal after the
seal, and then aborted while assembling the bundle: the actor process called
`is_file()` on the evaluator user's 0700 ledger path and got
`PermissionError`.  Its registry sealed `ABORTED_NO_RERUN` with terminal
`INCONCLUSIVE_MEASUREMENT_NOT_READY` (wrapper receipt `6de8dbd9…59bf5`,
archive `e1133da9…4c0e6`).  This is an instrument defect, not a model outcome;
the reveal of that protocol is now public, so the fix (the ledger digest is
optional under separate custody) was rerun within 24 hours under a fresh seed,
reveal, and registry in the same family (SR-3).  Both attempts are recorded in
the public projection.

## 5. Custody boundary

The evaluator seed, reveal, and ledger live under `hswm-evaluator` (0700); the
actor process could not read the reveal before the run (preflight
`ACTOR_CANNOT_READ_REVEAL_BEFORE_RUN`) nor stat the ledger after it.  The
actor account holds passwordless sudo on the DGX, so this is OS-user
separation with mechanical readability checks, not privilege separation.
That is the declared G0-local ceiling; G0-external stays a deferred
publication gate until a second party is named.

## 6. Independent structural verification

`results/raw/hswm_g1_opaque_identifiability_v3_2026-09-06/independent_verification.json`
replays the frozen-file join (bundle ↔ protocol ↔ registry seal), the
per-episode bundle reconstruction, and the DGX final attestation and
restoration join: `VALID_V3_FROZEN_FILES_ONE_SHOT_SEAL_AND_DGX_FINAL_ATTESTATION_JOIN`,
320 successful generation requests, shared services restored after
quiescence.  It is a local structural replay by the same owner, not an
independently owned scientific adjudication.

## 7. Privacy and evidence boundary

Prompts, completions, salts, leakage canaries, correct action codes, Permit
keys, and per-episode ledgers stay in the private content-addressed archive on
durable storage.  The public artifacts are the redacted projection, the
verification join, this narrative, and the evidence record; each is
content-addressed in
`evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_2026-09-06.json`.

## 8. Scientific boundary and next step

The fractal status is unchanged: `SCIENTIFICALLY_CONNECTED /
INTEGRATED_CLAIM_UNJUDGED`.  G0 is `NOT_PASSED`; G1 is `NOT_EVALUATED`; the
eight FCL laws, HSWM-of-HSWMs composition, consciousness, selfhood, and
scale-invariant causal closure were not tested; the live KG was not mutated by
the occurrence.  S-3 is complete as a run, not as a pass.  The next
preregistration in this family should state its no-state control as a
within-stratum contrast rather than a per-stratum ceiling, and must be frozen
before any further occurrence.
