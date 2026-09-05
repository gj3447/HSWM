# HSWM opaque-action identifiability v3 (G0-local) — draft, not frozen

Status: `DRAFT_NOT_FROZEN / NOT_EXECUTED / G0_LOCAL_CANDIDATE / G0_EXTERNAL_DEFERRED / G1_LOCKED`.
Closure step: S-3 of the
[closure plan](../../../../docs/research/HSWM_ADVERSARIAL_AUDIT_AND_CLOSURE_PLAN_2026-09-05.md)
under the ratified decision D-1 (G0-local / G0-external split).

This directory intentionally contains no `protocol.v1.json` yet. The v3
protocol is generated together with its secret evaluator reveal from a seed
that only the evaluator OS user holds, so the public protocol can only be
produced on the run host. Committing a protocol generated from a seed the
actor has seen would defeat the evaluator custody boundary.

## What v3 adds over the 2026-08-30 v2 occurrence

| G0-local criterion (D-1) | v3 mechanism |
|---|---|
| evaluator in a separate process under a separate OS user with a separate key | `hswm.experiments.g1_opaque_evaluator_process`: one salt-keyed HMAC reply per episode, own append-only ledger, reported uid |
| precommitted reveal | `evaluator_reveal_contract.reveal_commitment_root` and `generation.seed_commitment_sha256` are public; the reveal is read by the actor only after every call is sealed |
| randomized candidate position, stratified analysis | 16/16 correct-position balance from the seed; no-state arms reported per position stratum |
| outcome-independent sham | `OUTCOME_INDEPENDENT_SHAM` arm admits a disposition from a precommitted 16/16 bit that never saw the outcome |
| sealed trajectory before outcome | unchanged from v2 |
| exact remove/restore | unchanged from v2 |
| all-run manifest | one-shot registry; a VOID is repaired and rerun within 24 hours under this family (SR-3) |
| real Atom v2 Permit path (D-4 done-state) | every credited admission crosses `canonical-atom-v2-local-permit-commit-process` (S-2) |

Thirty-two episodes, ten calls each: 320 completions, 320 tokenizer
preflights, 640 loopback POSTs, 96 local Permit commits.

## Freeze procedure on the run host

1. As the evaluator user, create a private 64-byte seed and generate:

   ```sh
   head -c 64 /dev/urandom > /home/hswm-evaluator/private/v3-seed.bin
   uv run --locked python scripts/generate_hswm_g1_opaque_v3.py \
     --seed-file /home/hswm-evaluator/private/v3-seed.bin \
     --study-date 2026-09-15 \
     --live-binding-from _research/causal_composition/preregistrations/g1_opaque_identifiability_pilot_v2_2026-08-30/protocol.v1.json \
     --registry-path /mnt/hswm/evidence/hswm-g1-opaque-v3-2026-09-15-consumption-v1 \
     --protocol-out _research/causal_composition/preregistrations/g1_opaque_identifiability_v3_2026-09-15/protocol.v1.json \
     --reveal-out /home/hswm-evaluator/private/v3-reveal.json
   ```

   The reveal and seed stay mode 0600 under the evaluator user. The actor
   user must not be able to read them; the v3 preflight refuses otherwise.
2. Measure the offline tokenizer receipt for the thirty-two code pairs in the
   pinned image with Docker network `none` (the v2 procedure) and write it
   into `tokenizer_binding` with `status: MEASURED`.
3. Set `freeze.status` to `FROZEN`, commit the protocol and this README with
   the canonical and file SHA-256 of the protocol, and bind the reveal outer
   object to the frozen protocol digest.
4. Run the zero-POST preflight, then the occurrence once:

   ```sh
   uv run --locked python -m hswm.experiments.g1_opaque_v3 \
     --protocol <frozen protocol> --output-dir <fresh dir> \
     --execution-registry /mnt/hswm/evidence/hswm-g1-opaque-v3-2026-09-15-consumption-v1 \
     --runtime-binding <DGX runtime binding record> \
     --evaluator-argv-prefix 'sudo -n -u hswm-evaluator /opt/hswm/.venv/bin/python -m hswm.experiments.g1_opaque_evaluator_process' \
     --evaluator-reveal /home/hswm-evaluator/private/v3-reveal.json \
     --evaluator-ledger /home/hswm-evaluator/private/v3-ledger.jsonl \
     --reveal-after-seal /mnt/hswm/evidence/v3-reveal-after-seal.json \
     --preflight-only
   ```

   After the run the evaluator user copies the reveal to the
   `--reveal-after-seal` path; the instrument reads it only after all 320
   calls are sealed and then verifies every feedback bit with the salt.
5. Check in `results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_RESULTS_<date>.md`,
   `evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_<date>.json`, and one
   `F1_R8_RESULTS_LOG.md` row. That row is the S-3 completion evidence.

## Preregistered rule

The terminal `V3_COMPLETE_G0_LOCAL_IDENTIFIABILITY_OBSERVED_NO_EFFICACY_INFERENCE`
requires, out of 32: ACTIVE and RESTORE correct at least 30; FORCED_OPPOSITE
correct at most 2; each no-state arm (sham, NO_UPDATE, REMOVE) correct at most
21 overall and at most 12 in each position stratum of 16; `delta_state` at
least 0.5; 32 exact remove/restore transitions; 32 credited admissions in each
stateful arm; 96 Atom v2 Permit commits; 16/16 position and sham balance; and
32 salt-verified evaluator replies. Anything else is
`V3_COMPLETE_NO_SEPARATION_NO_EFFICACY_INFERENCE` or
`INCONCLUSIVE_MEASUREMENT_NOT_READY`.

An observed terminal is a `MEASUREMENT_READY_SINGLE_OWNER` candidate under the
declared opaque task. It is not G0-external, not G1, not a reuse-first
comparison, and not HSWM cognition, learning, or efficacy evidence. The rule,
thresholds, and prose are enforced byte-exactly by
`hswm.experiments.g1_opaque_v3.validate_v3_protocol`.
