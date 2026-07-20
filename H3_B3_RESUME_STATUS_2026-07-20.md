# H3-B3 resume status — 2026-07-20

## Verdict

H3-B3's corrected segments, PRE_RUN attestations, and pinned Qwen35 deployment
are now bound by a current schema-v2 manifest. Development extraction is
OPEN and running under that manifest. Fresh production remains forbidden until both
development certificates pass and the transition receipt is frozen. There is
still no H3-B3 efficacy result.

The checked-in `H3_B3_RUN_MANIFEST_2026-07-20.json` and
`H3_B3_RUN_MANIFEST_V2_2026-07-20.json` are historical receipts. The current
loader rejects them. Preserve them; do not resume from them or merge their
partial caches into a new run.

## Repaired provenance boundary

`h3_b3_prepare.py` previously sorted `gold_source_ids` by content hash while
the evaluator sidecar preserved candidate occurrence order. It also preserved
two trailing-space 2Wiki questions that the source-bound evaluator normalizes.
Current code now:

- orders gold evidence by the first occurrence of each deduplicated candidate;
- normalizes question whitespace exactly once; and
- has regressions for both multi-support order and question normalization.

Post-fix source-bound comparison:

| segment | rows | provenance mismatches |
|---|---:|---:|
| MuSiQue development | 200 | 0 |
| 2Wiki development | 200 | 0 |
| MuSiQue fresh | 300 | 0 |
| 2Wiki fresh | 250 | 0 |

## Local operator receipts (ignored, not efficacy evidence)

These paths live under `.ab_p5_cache/h3_b3/` and are intentionally outside the
Git evidence surface. Hashes are recorded here so an operator can detect drift
before freezing a new manifest.

| artifact | SHA-256 |
|---|---|
| `musique_development_v4_segment.json` | `de481a3307d8e04f17895b6c125f06a2299a821fc9254b67066058476b0b94e2` |
| `2wiki_development_v4_segment.json` | `10439ba55f0741fb2a092ce1dfb1fd0643cf1d0c5f42ff81dc001519608fd9fa` |
| `musique_fresh_v4_segment.json` | `214d5594e6b7437f3f7a95b1bd86656f2052c0badfe2815ccff222c3eaa545c8` |
| `2wiki_fresh_v4_segment.json` | `0b6b7f58abcce938ee4ed8e0e437d23af8b7d65399b8c8ff7075279206a01b97` |
| `development_extraction_input_v4.jsonl` (3,599) | `53d827704e530d91a7847a193735718ea9df36f8fe421feaaa61393f3193d114` |
| `development_embedding_input_v4.jsonl` (3,999) | `99e44c8fd5b7d3935ab4299e0510d620643dd82a4e0ee47a389d078d739b44f4` |
| `fresh_extraction_input_v4.jsonl` (5,449) | `9bccc338c1d1c8738ab1ea78f6283a462a278516c96b7b9d6832902041892942` |
| `fresh_embedding_input_v4.jsonl` (5,999) | `4b744d61a571d5cee122ad031a27535c529ab4c40703bfebda9b8c5a446a23bd` |
| `QWEN35_DEPLOYMENT_RECEIPT_V2_2026-07-20_RETRY1.json` | `15d3880b211c5e21a4087caa55f008d4474323a3d220e05bb47343bcd1f1c0a6` |

Post-fix preflight:

- 9/9 gates passed;
- receipt ID
  `hswm:h3_b3_preflight_receipt:v1:13d5d4c2473386ddc1d12e3e98c0c7b7e8f7a6e3e35b07877fba5976d18883f8`;
- receipt body SHA
  `1fc3635d5f5135658ee09bdc42d015b6d956fd2e1ae0f7f5ade2b08c33f4313a`;
- local file: `H3_B3_PREFLIGHT_RECEIPT_V3_2026-07-20.json`.

BGE-M3 snapshot attestation:

- revision `5617a9f61b028005a4858fdac845db406aefb181`;
- weight blob
  `b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38`;
- attestation ID
  `hswm:model_snapshot:v2:dc07a69754240aff08f42708ea3dbdeb405b17dc9d48e44ed79603a41f7511ac`;
- local file SHA
  `430ea4606b734d97ee8e07fe7a079ce8fcd18e77f6457a9f4cb95c3340824212`.

## Remote model status

The guarded Precision 7960 retry `hswm-qwen35-serve-20260720-r1` is serving
`Qwen/Qwen3.6-35B-A3B-FP8@95a723d08a9490559dae23d0cff1d9466213d989`
with `--max-num-seqs 32` at remote `127.0.0.1:18002`. The Mac tunnel exposes
the byte-identical endpoint as `http://127.0.0.1:18002/v1`. `/v1/models`
advertises exactly the pinned alias, and a local `temperature=0`, `seed=0`,
thinking-disabled probe returned exactly `OK`.

Deployment receipt:

- ID
  `hswm:model_deployment:v2:708f23ed73ed15bc5f9e3e8e9440c5d5c2b006bdc191c972516a2c4d1f9a0340`;
- local ignored path
  `.ab_p5_cache/h3_b3/QWEN35_DEPLOYMENT_RECEIPT_V2_2026-07-20_RETRY1.json`;
- file SHA
  `15d3880b211c5e21a4087caa55f008d4474323a3d220e05bb47343bcd1f1c0a6`.

## Current frozen manifest

`H3_B3_RUN_MANIFEST_V3_2026-07-20.json` is the exclusive-created current
manifest. It has status `PRE_RUN_FROZEN`, file SHA
`7f9ec247afbdd11066706837a921159da6480d1c013995dea23b7c3907c284bb`,
and unused output prefix
`.ab_p5_cache/h3_b3/runs/qwen35-r1-schema-v2-20260720`. It binds:

- the corrected v4 development and fresh segments;
- the V3 9/9 preflight receipt and BGE-M3 snapshot attestation;
- the live Qwen35 deployment receipt and pinned revision;
- batch-size-1 extraction with concurrency 2; and
- all development/fresh future paths before any output existed.

## Current development production (in progress)

At `2026-07-20 18:17:37 KST`, development extraction was live with 25 of
3,599 paragraph attempt rows durably appended. This is progress evidence, not
an efficacy result or a completed artifact.

- OMD production lease: `orb-b7fdc1537193`, fence `131`, covering only the
  three committed development extraction lifecycle paths;
- OPEN receipt ID
  `hswm:h3_artifact_open:v1:5b5c1dc49467f428c469f64c578157099d0dea7e5caa61a250b60b089fa85eb3`;
- OPEN receipt file SHA
  `a5c008974bcdc56ced1702d9d23f909d96f6d49aa7731917afb9ac718bad6b63`;
- reserved extraction inode `410657328`;
- local supervisor: tmux session `hswm-h3-dev-extract`, pane PID `59080`;
- completion log: `/tmp/hswm-h3-b3-dev-extraction-20260720-tmux.log`.

The producer is resumable. A process interruption leaves completed fsynced
attempt rows on the same reserved inode. Re-running the byte-identical command
uses terminal rows as cache hits and retries only ERROR/nonterminal sources.
Do not first-write `extractions.close.json` until the producer exits 0 and the
full 3,599-source domain loader succeeds.

## Valid next sequence

1. Preserve the frozen code, preflight, deployment receipt, manifest, OPEN
   receipt, reserved inode, and output prefix. Any drift requires a new
   exclusive-created evidence chain.
2. Let the current development extraction finish. On exit 2 or interruption,
   rerun the identical producer command; do not replace the JSONL.
3. Domain-validate and CLOSE extraction, then separately OPEN, produce,
   domain-validate, and CLOSE the guarded Precision BGE-M3 embedding bundle.
4. Run `h3_b3_falsifier.py --phase development` only.
5. If either development certificate refuses, record the refusal and stop.
   Fresh production is allowed only after both development certificates pass
   and a transition receipt is frozen.

The existing 434-row extraction cache is not legally resumable under this
sequence. A newly OPENed schema-v3 cache from the new manifest will be.
