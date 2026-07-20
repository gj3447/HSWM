# H3-B3 resume status — 2026-07-20

## Verdict

H3-B3's corrected segment/preflight side is ready for the remaining PRE_RUN
attestations, not yet for a manifest freeze or fresh evaluation. The
implementation and nine preflight mechanism gates pass, but no current
schema-v2 manifest binds a live Qwen deployment to the corrected segments.
There is no H3-B3 efficacy result.

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

The isolated Precision 7960 launch of
`Qwen/Qwen3.6-35B-A3B-FP8@95a723d08a9490559dae23d0cff1d9466213d989`
loaded the model but did not become a serving endpoint. vLLM rejected default
`max_num_seqs=1024` because only 630 Mamba cache blocks were available. The job
exited with `rc=1`; `dt ls` reports no running HSWM jobs. A retry should set
`--max-num-seqs 32`, then generate the deployment receipt against the exact
endpoint used by the extractor.

No live Qwen deployment receipt exists yet. Therefore a new confirmatory
manifest must not be frozen and extraction must not start.

## Valid next sequence

1. If any frozen H3 implementation module changes, issue a new exclusive-create
   preflight receipt; never overwrite the V3 receipt.
2. Start the pinned Qwen35 revision with `--max-num-seqs 32` inside the guarded
   remote cgroup and verify `/v1/models` plus one deterministic request.
3. Generate the deployment receipt from the byte-identical extractor endpoint.
4. Build a new root-level schema-v2 manifest from the v4 segments, v2 fresh
   manifests, post-fix preflight, BGE attestation, and Qwen receipt. Use a wholly
   unused output prefix and batch size 1.
5. OPEN, produce, domain-validate, and CLOSE development extraction and
   embeddings through `h3_artifact_lifecycle.py`.
6. Run `h3_b3_falsifier.py --phase development` only.
7. If either development certificate refuses, record the refusal and stop.
   Fresh production is allowed only after both development certificates pass
   and a transition receipt is frozen.

The existing 434-row extraction cache is not legally resumable under this
sequence. A newly OPENed schema-v3 cache from the new manifest will be.
