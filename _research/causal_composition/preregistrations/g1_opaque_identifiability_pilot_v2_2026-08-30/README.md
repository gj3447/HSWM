# HSWM opaque-action identifiability successor freeze

This is a new exploratory G0 instrument-identifiability study, not a rerun of
the predecessor occurrence. It does not authorize a G1 efficacy claim or gate
promotion.

The canonical JSON SHA-256 of `protocol.v1.json` is
`eae768f3f42de345bfcc995a5effb085f39c1732bb956fa37c6eab08870a553d`.
The schema remains `hswm-g1-opaque-identifiability-pilot/v1` because the task,
arms, estimands, thresholds, episode set, and call schedule are unchanged. The
new occurrence has study UID
`sym:ExploratoryStudy:hswm-g1-opaque-identifiability-v2-2026-08-30` and durable
registry
`/mnt/hswm/evidence/hswm-g1-opaque-identifiability-pilot-v2-2026-08-30-consumption-v1`.

## Predecessor pre-claim failure

Wrapper run `g1-opaque-identifiability-9ff36ce-v1` failed after fresh-service
startup but before the execution registry claim and before
`run_exploratory_slice`. The pinned image has `/usr/bin/python3` but no bare
`python` executable; the launcher requested the latter for the offline
tokenizer measurement.

The exact wrapper receipt has SHA-256
`c0c211b5973289aaa51e2bec8a946a455fb0eb09eb1293cd91cbe928f43b2b82`.
Its 122,880-byte archive has SHA-256
`c3affb6c95cced2f7fb8673f81dedd5ca06b436654eaf9a87cf56f2aa7498ea6`.
The retained runtime-binding file has SHA-256
`c68114a17d302bc3ba5c4f75bdb6137e995f0e8fc56a8d672a8d8d75257eef4e`
and record SHA-256
`16951d79db2b36bede675b4d5a455066d5e0dcf4b6eb1d54a112e883f6ffe75e`.
It binds source commit `9ff36ce297553f53583e25a458b17d62d22ee4ed`,
the predecessor protocol digest, and startup generation-request count zero.
The console traceback joins the failure to the offline tokenizer Docker
invocation. The predecessor registry is absent, and no result, episode,
admission, completion POST, or `/tokenize` POST was produced.

These artifacts are retained byte-exactly under
`artifacts/g1_opaque_identifiability/operational_failure/` and are operational
provenance only. They are not a scientific result, G0 observation, G1
observation, or evidence of zero efficacy. The failed wrapper archive contains
no final teardown/restoration attestation, so a later observation that the
shared containers were running is not promoted into an exact restoration
claim.

## Carry-forward rule

No model-visible request or behavioral observation existed to condition task
selection. Therefore the eight public episodes, evaluator secrets, ordered
entry commitments, and reveal commitment root
`71ac26c3bb586b026747acf9f311e4cb4e89be0fd6389cbdd58828f2b0d36620`
are carried forward without replacement or adaptation. The external reveal
outer object must instead bind the new study UID and new protocol digest. The
predecessor outer reveal file and any pre-freeze successor draft are invalid.
The frozen external reveal is
`/mnt/hswm/evidence/hswm-g1-opaque-evaluator-reveal-v2-eae768f3.json`, 2,383
bytes, with SHA-256
`3a7e7afb5b779e114ef9cb7b089300e2cc942c5e2f1852304d946f63835f670d`.

## Bootstrap qualification

The frozen launcher invokes `/usr/bin/python3` in the pinned image with Docker
network `none`. Both `--preflight-only` and the live entrypoint reproduce and
validate the complete offline tokenizer receipt before any shared-service
stop, fresh model launch, registry claim, or behavior POST. The preflight uses
one ephemeral network-isolated container; it does not stop the shared
services. A tokenizer failure ends before the fresh-runtime context is entered.

Diagnostic wrapper run `g1-opaque-tokenizer-diag-9ff36ce-v1` reproduced the
missing bare `python` executable (receipt SHA-256
`f196677dbdab8e2a2d2403f030b203d92d2e412f345d9a83cfc234e16f62d040`,
archive SHA-256
`10e24db0e36ded56c81c8128d58e42fc5b8a67cf4057cd5557945c4eeaae6393`).
Run `g1-opaque-tokenizer-diag-9ff36ce-v2` observed `/usr/bin/python3` in the
same image and succeeded (receipt SHA-256
`92a32583779279cb197b73e497608c480059ab905d47da8bed818cb92fce8fae`,
archive SHA-256
`27995aeef4c2a47366bc5157e15fd30397be02ab7481c2f507356362e01040fc`).
Their exact receipts and archives are retained under
`artifacts/g1_opaque_identifiability/bootstrap_diagnostics/`. These
diagnostics observed no task behavior.

The byte-exact operational archives retain runtime host and filesystem-path
metadata, as existing checked-in DGX evidence does. A scan found no credential,
evaluator reveal, salt, canary, correct-action mapping, or task-response value;
the path metadata is intentionally retained rather than redacted so the
recorded hashes remain reproducible.

## Frozen occurrence

The successor retains exactly eight episodes and the branches ACTIVE,
FORCED_OPPOSITE_FEEDBACK, NO_UPDATE, REMOVE, and RESTORE. It permits 64
completion POSTs and 64 `/tokenize` POSTs in the frozen per-episode order, with
no retry, refill, resume, replacement, adaptation, partial-look decision, or
second occurrence. FORCED_OPPOSITE_FEEDBACK remains an outcome-dependent
counterfactual control, not the outcome-independent sham required by a later
complete G1 experiment.

The positive terminal and all descriptive estimands are unchanged from the
predecessor freeze. Any structurally complete non-separation is retained as
such. Any call, parser, or structural failure consumes this successor registry
and yields an inconclusive measurement.

Run the zero-behavior-POST DGX preflight first:

```sh
~/bin/hswm-run exec HSWM_G1_OPAQUE_V2_PREFLIGHT_RUN_ID --profile hswm \
  --cwd . -- uv run --locked python -m hswm.experiments.g1_micro_dgx \
  --protocol _research/causal_composition/preregistrations/g1_opaque_identifiability_pilot_v2_2026-08-30/protocol.v1.json \
  --model-snapshot MODEL_SNAPSHOT \
  --lock-path /mnt/hswm/evidence/hswm-g1-micro-dgx.lock \
  --execution-registry /mnt/hswm/evidence/hswm-g1-opaque-identifiability-pilot-v2-2026-08-30-consumption-v1 \
  --evaluator-reveal EXTERNAL_SUCCESSOR_EVALUATOR_REVEAL \
  --preflight-only
```

Only after a clean source freeze, focused and full validation, independent
audit, green CI, and that preflight may the same command be issued once without
`--preflight-only`, under a new wrapper run ID.

The scientific ceiling remains
`EXPLORATORY_G0_IDENTIFIABILITY_ONLY_NOT_G1_EFFICACY_OR_GATE`. The local permit
and state are not canonical HSWM admission or HSWM cognition. This study does
not test the eight FCL laws, recursive HSWM-of-HSWMs composition,
consciousness, selfhood, or scale-invariant causal closure, and it does not
mutate the live KG.
