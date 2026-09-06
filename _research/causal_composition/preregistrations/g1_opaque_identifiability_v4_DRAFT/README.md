# HSWM opaque-action identifiability v4 (G0-local) — family template

Status: `FAMILY_TEMPLATE / DESIGN_REVISION_OF_V3 / EXECUTED_ONCE_ON_2026-09-06_RULE_NOT_MET / G0_EXTERNAL_DEFERRED / G1_LOCKED`.

Executed: [`v4_2026-09-06`](../g1_opaque_identifiability_v4_2026-09-06/protocol.v1.json) → `V3_COMPLETE_NO_SEPARATION_NO_EFFICACY_INFERENCE` ([results](../../../../results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V4_RESULTS_2026-09-06.md)); the control clause was shown unsatisfiable and v5 followed.
Closure step: a further S-3 occurrence under the ratified decision D-1, chosen
under the user's delegated 2026-09-06 decision
([source](../../../../docs/canon/sources/USER_PRIMARY_HSWM_CLOSURE_DECISIONS_2026-09-06.txt)).

This directory intentionally contains no `protocol.v1.json`; frozen protocols
live in dated siblings (`g1_opaque_identifiability_v4_<date>[-rN]/`).

## What v4 changes, and what it does not

The v3 occurrence of 2026-09-06 ([results](../../../../results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_RESULTS_2026-09-06.md))
met every clause of its frozen rule except the per-position-stratum ceiling
for the no-state arms: NO_UPDATE and REMOVE were correct in 16/16 of the
position-1 stratum and 0/16 of the position-2 stratum.  The cause is a design
coupling, not a rule defect: v3 derived the NO_UPDATE order as the reverse of
the stateful order and the REMOVE order as identical to it, so a model that
answers no-state probes by a fixed candidate position is correct in exactly one
whole stratum.  Under that coupling the ceiling can never be satisfied by a
positional default, and the ceiling exists precisely to detect one.

v4 keeps the instrument, schema, terminals, evaluator custody, sham arm,
Permit path, tokenizer binding, code-pool selection, and the identifiability
rule byte-for-byte.  The only change is generative: the NO_UPDATE and REMOVE
candidate orders are drawn from the seed independently of the stateful order
and balanced within each stateful position stratum (8 correct-first, 8
correct-second in each stratum of 16, for each arm).  A positional default
now expects 8/16 per stratum, well under the ceiling of 12, so the rule
measures state mediation rather than order coupling.  The protocol records
`generation.design_revision = "v4"`, the order policy, and the per-stratum
balance; `study_uid` carries the `-v4-` family marker.

This is a new preregistration (RG-4).  The v3 result stands as sealed; nothing
here rescores it.

## Freeze and run procedure

Identical to the v3 family README, with `--design v4` on the generator and the
`v4` dated directory:

```sh
# evaluator user: pool, then (after the actor measures it) the protocol and reveal
sudo -n -u hswm-evaluator <venv>/python scripts/generate_hswm_g1_opaque_v3.py --design v4 --emit-code-pool <pool> ...
sudo -n -u hswm-evaluator <venv>/python scripts/generate_hswm_g1_opaque_v3.py --design v4 --token-counts <counts> \
  --study-date <YYYY-MM-DD> --live-binding-from <v2 protocol> \
  --registry-path /mnt/hswm/evidence/hswm-g1-opaque-v4-<YYYY-MM-DD>-consumption-v1 \
  --protocol-out <draft> --reveal-out /home/hswm-evaluator/private/v4-reveal.json
# actor: measure-pool, measure (freeze); evaluator: rebind-reveal, publish-after-seal
# actor: python -m hswm.experiments.g1_micro_dgx --protocol .../g1_opaque_identifiability_v4_<date>/protocol.v1.json ...
```

## Preregistered rule

Unchanged from v3 and enforced by `hswm.experiments.g1_opaque_v3.validate_v3_protocol`:
out of 32, ACTIVE and RESTORE correct at least 30; FORCED_OPPOSITE correct at
most 2; each no-state arm (sham, NO_UPDATE, REMOVE) correct at most 21 overall
and at most 12 in each stateful position stratum of 16; `delta_state` at
least 0.5; 32 exact remove/restore transitions; 32 credited admissions in each
stateful arm; 96 Atom v2 Permit commits; 16/16 position and sham balance; 32
salt-verified evaluator replies.  An observed terminal is a
`MEASUREMENT_READY_SINGLE_OWNER` candidate under the declared opaque task; it
is not G0-external, not G1, not a reuse-first comparison, and not HSWM
cognition, learning, or efficacy evidence.
