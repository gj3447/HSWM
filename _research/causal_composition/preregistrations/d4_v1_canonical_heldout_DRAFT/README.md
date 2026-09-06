# D-4 held-out successor — unresolved implementation contract

Status: `DRAFT_NOT_FROZEN_NOT_EXECUTED / D4_V1_NOT_COMPLETE`.
Authority: `SECONDARY_AI_RESEARCH_DESIGN`.

The ratified D-4 milestone requires one checked-in G0-local run linking
independently produced outcome, credit, a durable canonical revision through
the real Atom v2 Permit path, changed held-out behavior, removal,
byte-identical restoration and sham. This draft identifies what an executable
successor still needs. It is not a new experiment or a completion judgment.

## Conceptual delta from opaque v5

The current store is experiment-local. The
[`Atom v2 bridge`](../../../../src/hswm/experiments/atom_v2_permit_bridge.py)
commits an exact transition through the real local Permit process, but its
explicit boundary is `NOT_CANONICAL_HSWM_ADMISSION`. A fsync'd receipt or a new
name for that store does not close D-4's canonical revision requirement.

Likewise, v5's `OPAQUE_ACTION_CODE_DISPOSITION` compiler reads the exact cue
from the same episode. Correct codes are independently derived across
episodes. A different candidate order is another response probe; a new cue
has neither a matching readset nor a declared relation to the learned code.
There is no untouched held-out task evaluation in the v5 result.

A successor therefore needs two substantive changes:

1. a declared study schema, ownership obligations and persistence/commit
   semantics that make the tested revision canonical within the declared
   study, with explicit limits relative to HSWM admission;
2. task-level disposition semantics that apply to genuinely fresh instances
   sharing a prospectively declared relation with training instances.

These are changes to the tested state and task semantics, not a promotion of
v5. The full HSWM target and D-4 success requirements remain unchanged.

## Required implementation before a prospective freeze

| Missing boundary | Concrete implementation obligation |
|---|---|
| Task and holdout | Select a task family and disjoint train/final-heldout partition before content or outcomes are inspected. Define why a learned revision can apply to an unseen instance without containing its answer. |
| Study schema | Declare admitted atom kinds, typed references, immutable version/lineage identity and exactly one responsibility owner per atom. Proposer, evaluator, executor and custodian roles do not automatically determine that owner. |
| Outcome and credit | Seal the emitted trajectory before the separate evaluator returns its outcome. Bind credit to both and verify the proposed revision against that credit. |
| Canonical commit | Bind owner, parent head, schema, transition invariant and actual Permit decision to the same revision bytes. Admit only after successful verification; preserve failed proposals separately. |
| Persistence | Recover the same state in a fresh process. Retain immutable revision and head bytes with a verifiable pre/post chain. A current local Permit slot alone is insufficient. |
| Compiled behavior | Record the revision IDs and compiled bytes used by every held-out call. Keep evaluator material, labels and raw training answers out of the compiler readset. |
| Interventions | ACTIVE, NO_UPDATE, outcome-independent SHAM, SHUFFLED_CREDIT, REMOVE and RESTORE use matched task/runtime/budget surfaces. REMOVE selects the exact pre-revision state; RESTORE selects byte-identical ACTIVE state. |
| All-run accounting | Preserve invalid and aborted prefixes, issued failed calls, costs and terminal status. Never replace or resume a consumed occurrence. |

The exact schema and task remain unselected. This document does not impose a
new fixed subsystem/owner decomposition, choose an ALFWorld cohort, or admit
anything to canonical HSWM state. B0/B2 remain secondary comparators under D-3.

## Success rule and evidence limits

Before a run, freeze sample sizes, margins, denominators, seeds, analysis,
source/runtime identities and stopping rules. The final held-out comparison
must show the preregistered ACTIVE effect, its elimination by REMOVE and
recovery by RESTORE, and failure of SHAM/SHUFFLED_CREDIT to reproduce it.
Every claimed revision must have a reconstructible outcome-to-credit-to-
owner/Permit-to-canonical-state-to-compiled-behavior chain.

Instrument failures remain inconclusive. A valid negative result retires or
reroutes its exact mechanism family with evidence intact. No task, threshold
or denominator may be changed after outcome inspection to produce success.
Meeting D-4 would establish its finite declared milestone only, not
G0-external, G1, general HSWM efficacy or fractal cognitive closure.

The v3/v4/v5 frozen protocols, results and ceilings remain unchanged. This
unexecuted draft creates no research receipt, F1_R8 result or KG event.
