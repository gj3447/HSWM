# HSWM opaque-action identifiability v5 (G0-local) — family template

Status: `FAMILY_TEMPLATE / RULE_REVISION_OF_V4 / G0_LOCAL_CANDIDATE / G0_EXTERNAL_DEFERRED / G1_LOCKED`.
Closure step: a further S-3 occurrence under D-1, chosen under the user's
delegated 2026-09-06 decision
([source](../../../../docs/canon/sources/USER_PRIMARY_HSWM_CLOSURE_DECISIONS_2026-09-06.txt)).
Frozen protocols live in dated siblings (`g1_opaque_identifiability_v5_<date>[-rN]/`).

## Why a rule revision

Two sealed occurrences, [v3](../../../../results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_RESULTS_2026-09-06.md)
and [v4](../../../../results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V4_RESULTS_2026-09-06.md),
met every clause of the frozen rule except one: a no-state arm may be correct
in at most 12 of the 16 episodes of each position stratum.  v4 made the
no-state orders independent of the stateful order and the pattern did not
move: NO_UPDATE and REMOVE were correct in 16/16 of the episodes where the
correct code was first in the arm's own order and 0/16 where it was second.
A strict first-candidate default produces exactly that split for any order,
so the clause cannot be satisfied by a control that behaves as a control
(chance overall, position-determined).  It was a preregistration defect in
the control clause, invisible in the eight-episode coupled v2 design.

## What v5 changes

Everything about the instrument, custody, sham arm, Permit path, tokenizer
binding, code-pool selection, balanced independent no-state orders (from v4),
terminals, and claim ceiling is unchanged.  Only the rule's control clause is
replaced:

| Clause | v3/v4 | v5 |
|---|---|---|
| ACTIVE, RESTORE pooled | ≥ 30 / 32 | ≥ 30 / 32 |
| FORCED_OPPOSITE pooled | ≤ 2 / 32 | ≤ 2 / 32 |
| SHAM, NO_UPDATE, REMOVE pooled | ≤ 21 / 32 each | ≤ 21 / 32 each |
| per-stratum control clause | each no-state arm ≤ 12 / 16 in each **own-position** stratum | ACTIVE and RESTORE ≥ 15 / 16 in each **stateful-position** stratum; FORCED_OPPOSITE ≤ 1 / 16 per stateful stratum; the no-state own-position pattern is reported, not gated |
| `delta_state` | ≥ 0.5 | ≥ 0.5 |
| structural counts | 32 admissions per stateful arm, 96 Permit commits, 32 exact remove/restore, 16/16 balances, 32 verified feedback bits | same |

The stateful-arm floors are stronger than before (v3/v4 gated the stateful
arms only pooled); the control clause moves from an unsatisfiable own-position
ceiling to pooled chance-plus-margin ceilings that a leaking control would
exceed (a control that is correct in more than 21 of 32 episodes fails).
The rule is `hswm.experiments.g1_opaque_v3.IDENTIFIABILITY_RULE_V5`, embedded
in `analysis.g0_local_identifiability_rule` of every v5 protocol and enforced
byte-exactly by `validate_v3_protocol`.

This is a new preregistration (RG-4).  The v3 and v4 terminals stand; nothing
here rescores them.  Under the v5 rule the v3/v4 pattern would have been
observed, which is exactly why the rule change had to be frozen before a new
occurrence rather than applied to the old ones.

## Procedure

Identical to v3/v4 with `--design v5` on the generator and the `v5` dated
directory; see the v3 family README for the seven steps.
