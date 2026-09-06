# HSWM opaque-action identifiability v3 (G0-local) — draft, not frozen

Status: `FAMILY_TEMPLATE / EXECUTED_ONCE_ON_2026-09-06 / G0_LOCAL_CANDIDATE / G0_EXTERNAL_DEFERRED / G1_LOCKED`.

Executed occurrences of this family (frozen protocols live in their dated
sibling directories, never here):

| Protocol | Registry | Terminal | Record |
|---|---|---|---|
| [`v3_2026-09-06`](../g1_opaque_identifiability_v3_2026-09-06/protocol.v1.json) | `hswm-g1-opaque-v3-2026-09-06-consumption-v1` | `INCONCLUSIVE_MEASUREMENT_NOT_READY` (all 320 calls sealed, reveal published, then an actor-side stat of the evaluator-private ledger aborted bundle assembly) | recorded in the r2 projection as the aborted attempt |
| [`v3_2026-09-06-r2`](../g1_opaque_identifiability_v3_2026-09-06-r2/protocol.v1.json) | `hswm-g1-opaque-v3-2026-09-06-r2-consumption-v1` | `V3_COMPLETE_NO_SEPARATION_NO_EFFICACY_INFERENCE` | [`results`](../../../../results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_RESULTS_2026-09-06.md) |
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

## Freeze and run procedure on the run host (2026-09-06 tooling)

The run host is the DGX (`edgexpert-e229`, NVIDIA GB10
`GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5`, the same GPU, image and model
snapshot the v2 occurrence bound).  The actor is the interactive DGX user; the
evaluator is the dedicated OS user `hswm-evaluator`.  Every step below is
zero-POST until step 6.

1. **Generate (evaluator user).**  The seed and the reveal never leave the
   evaluator's private directory; the public draft protocol is written into
   the checkout under the dated path.

   ```sh
   sudo -n -u hswm-evaluator sh -c 'umask 077; head -c 64 /dev/urandom > /home/hswm-evaluator/private/v3-seed.bin'
   sudo -n -u hswm-evaluator /opt/hswm/.venv/bin/python scripts/generate_hswm_g1_opaque_v3.py \
     --seed-file /home/hswm-evaluator/private/v3-seed.bin \
     --study-date <YYYY-MM-DD> \
     --live-binding-from _research/causal_composition/preregistrations/g1_opaque_identifiability_pilot_v2_2026-08-30/protocol.v1.json \
     --registry-path /mnt/hswm/evidence/hswm-g1-opaque-v3-<YYYY-MM-DD>-consumption-v1 \
     --protocol-out _research/causal_composition/preregistrations/g1_opaque_identifiability_v3_<YYYY-MM-DD>/protocol.v1.json \
     --reveal-out /home/hswm-evaluator/private/v3-reveal.json
   ```

2. **Measure and freeze (actor user).**  `scripts/freeze_hswm_g1_opaque_v3.py
   measure` runs the offline tokenizer measurement for the thirty-two code
   pairs inside the pinned image with Docker network `none`, writes it into
   `tokenizer_binding` as `MEASURED`, sets `freeze.status` to `FROZEN`, and
   prints the draft and frozen canonical digests.  Unequal token counts or a
   non-draft protocol are refused before any write.

   ```sh
   uv run --locked python scripts/freeze_hswm_g1_opaque_v3.py measure \
     --protocol _research/causal_composition/preregistrations/g1_opaque_identifiability_v3_<YYYY-MM-DD>/protocol.v1.json \
     --model-snapshot <hf-cache>/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/95a723d08a9490559dae23d0cff1d9466213d989 \
     --frozen-on <YYYY-MM-DD>
   ```

3. **Rebind the reveal (evaluator user).**  The freeze changed the protocol's
   canonical digest; the reveal's outer `protocol_canonical_sha256` must name
   the frozen digest.  The commitment root excludes that field, so the
   thirty-two episode commitments in the public protocol are unchanged.

   ```sh
   sudo -n -u hswm-evaluator /opt/hswm/.venv/bin/python scripts/freeze_hswm_g1_opaque_v3.py rebind-reveal \
     --reveal /home/hswm-evaluator/private/v3-reveal.json \
     --protocol _research/causal_composition/preregistrations/g1_opaque_identifiability_v3_<YYYY-MM-DD>/protocol.v1.json
   ```

4. **Commit the frozen protocol** (and this README with the digests) so the
   DGX checkout is clean at a commit that contains it.  The launcher refuses a
   dirty checkout and re-hashes the protocol against `HEAD`.

5. **Zero-POST preflight (actor user, fresh lease not yet taken).**  The same
   launcher as v2 recognises the dated v3 path, re-measures the tokenizer
   receipt against the frozen binding, and runs the v3 custody/registry
   preflight.

   ```sh
   ~/bin/hswm-run exec HSWM_G1_OPAQUE_V3_PREFLIGHT_<YYYYMMDD> --profile hswm --cwd . -- \
     uv run --locked python -m hswm.experiments.g1_micro_dgx \
       --protocol _research/causal_composition/preregistrations/g1_opaque_identifiability_v3_<YYYY-MM-DD>/protocol.v1.json \
       --model-snapshot <hf-cache>/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/95a723d08a9490559dae23d0cff1d9466213d989 \
       --lock-path /mnt/hswm/evidence/hswm-g1-micro-dgx.lock \
       --execution-registry /mnt/hswm/evidence/hswm-g1-opaque-v3-<YYYY-MM-DD>-consumption-v1 \
       --evaluator-argv-prefix 'sudo -n -u hswm-evaluator /opt/hswm/.venv/bin/python -m hswm.experiments.g1_opaque_evaluator_process' \
       --evaluator-reveal-path /home/hswm-evaluator/private/v3-reveal.json \
       --evaluator-ledger /home/hswm-evaluator/private/v3-ledger.jsonl \
       --reveal-after-seal /mnt/hswm/evidence/hswm-g1-opaque-v3-<YYYY-MM-DD>-reveal-after-seal.json \
       --node "$HOME/.local/bin/node" \
       --preflight-only
   ```

6. **The occurrence, once.**  The same command without `--preflight-only`
   under a new wrapper run id.  The lease stops the shared containers,
   launches the digest-pinned loopback vLLM container with fresh caches,
   writes the runtime binding, runs the thirty-two episodes through the
   separate evaluator process and the built Atom v2 local Permit commit
   process, attests the final counters, tears down, and restores the shared
   services.  After the last call is sealed the evaluator user copies the
   reveal to the `--reveal-after-seal` path; the instrument verifies every
   feedback bit with the salts only then.

7. Check in `results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_RESULTS_<date>.md`,
   `evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_<date>.json`, and one
   `F1_R8_RESULTS_LOG.md` row.  That row is the S-3 completion evidence.

Custody note: the actor account on the DGX holds passwordless sudo, so the
evaluator boundary is OS-user separation with the preflight's readability
check, not privilege separation.  That is the declared G0-local ceiling
(`MEASUREMENT_READY_SINGLE_OWNER`); G0-external stays deferred.

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
