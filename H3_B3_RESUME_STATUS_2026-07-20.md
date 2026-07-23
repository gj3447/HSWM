# H3-B3 resume status — 2026-07-20

## Verdict

H3-B3 V3 was refused before efficacy after its sole identical retry left two
deterministic `finish_reason=length` errors.  V3 has no CLOSE, embedding,
development report, transition, or fresh output.  The refusal is frozen in
`H3_B3_V3_REFUSAL_2026-07-20.md`.

V4 extractor, preflight, manifest-builder, and loader hardening is complete.
The V4 preflight receipt and first-write run manifest are frozen and
independently reloadable, but V4 was refused before its first endpoint call.
Its extraction OPEN reserved a new empty inode; the harness then detected that
the CLOSE would commit only an accounting hash instead of publishing the
mandated values, and that non-2xx HTTP bodies were not preserved. V4 remains at
zero STARTs and zero endpoint calls. V5 is the active successor. Fresh remains
forbidden. There is still no H3-B3 efficacy result.

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

Historical V3 post-fix preflight (not admissible for V4):

The values below bind the V3 code root only.  The current loader correctly
rejects this receipt after V4 hardening; a new V4 preflight is still pending.

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

## Historical V3 manifest

`H3_B3_RUN_MANIFEST_V3_2026-07-20.json` is the exclusive-created historical
manifest. It has status `PRE_RUN_FROZEN`, file SHA
`7f9ec247afbdd11066706837a921159da6480d1c013995dea23b7c3907c284bb`
and output prefix
`.ab_p5_cache/h3_b3/runs/qwen35-r1-schema-v2-20260720`. It binds:

- the corrected v4 development and fresh segments;
- the V3 9/9 preflight receipt and BGE-M3 snapshot attestation;
- the live Qwen35 deployment receipt and pinned revision;
- batch-size-1 extraction with concurrency 2; and
- all development/fresh future paths before any output existed.

## V3 development refusal

The append-only V3 JSONL now has 3,602 rows at SHA-256
`bab9d5bb4d152c3f65e15f5fb2f876c37846fbb09aa101442c7b87f7ca54ef1b`.
The initial 3,599 calls left three length errors.  One identical retry made
exactly three endpoint calls: one recovered to `partial/stop`, and two repeated
the same length-truncated content.  Only 3,597 sources are compiler-admissible.

The V3 cache is no longer resumable.  Preserve its OPEN receipt, inode, and
JSONL exactly; never create its CLOSE.  Its OMD production task is ABORTED and
no live V3 write lease remains.

## V4 hardening completion

The restart code now fails closed across the previously identified provenance
and retry gaps:

- every endpoint attempt first appends and fsyncs a `START`; a matching
  `FINALIZE` preserves the raw response in the same append-only JSONL;
- an unmatched `START` consumes its ordinal, blocks CLOSE, and cannot be hidden
  by a later process restart;
- per-cache process locking prevents concurrent workers from exceeding the
  two-attempt cap while preserving within-process concurrency 2;
- the preflight runs all gates from a private read-only 20-file source snapshot
  and binds each result to its gate file and complete execution-source root;
- the builder and loader both enforce the one-off V4 protocol, extractor,
  segment, preimage, sidecar, holdout, output, and deployment commitments;
- the loader additionally revalidates the exact 1024-dimensional BGE contract,
  repository-root manifest filename, and both parent-evidence file hashes; and
- generic structural fixtures are isolated from the one-off constants, while
  dedicated tests prove the exact V4 baseline passes and self-consistent drift
  is rejected.

Current unfrozen source roots (inputs to the next preflight):

- implementation root:
  `e9831b393c1cfbcab1987e8919452a126d02e136b2e2b2814a0d703a6049cc7d`;
- complete execution-source root:
  `71f50a932e3400b06abfdb8a3744037c16badb4b25bd1e06e4a4c731447b7a04`;
- frozen three-gate source root:
  `2218428e2767689ebd538d99aad54031c8dcefdfc2913b43ed5e843f3513ddf5`.

Validation before artifact freeze: `428 passed`; targeted V4 hardening suite:
`85 passed`; `py_compile` and `git diff --check` both passed. No V4 endpoint
call was made during hardening.

## V4 frozen restart receipts

The new preflight ran all nine gates from the private source snapshot and
passed 9/9:

- path:
  `.ab_p5_cache/h3_b3/H3_B3_PREFLIGHT_RECEIPT_V4_2026-07-20.json`;
- file SHA-256:
  `d027f1e82a5c5065955f873796cbea4c6ba548a960c7cf782ec52edce16c571c`;
- receipt body SHA-256:
  `682b17829e1d776eafdf16aea812343ed28c6b58ec2d61dfc4f8bb2c7ec554bf`;
- receipt ID:
  `hswm:h3_b3_preflight_receipt:v1:6c11573b5009bd1f8e9cd2dfe2350e6faede56c5432cea8e9d8b84c91c7ed63d`.

The first-write manifest is `H3_B3_RUN_MANIFEST_V4_2026-07-20.json` at
SHA-256
`aca82aa77e81c15815562e4473ee4daae70778bba6e205cd78e5193a7c6a483c`.
The production loader accepted it with status `PRE_RUN_FROZEN`; no temporary
validation file remained and both development and fresh output prefixes were
still absent after publication.

Immediately before freeze, the existing Qwen35 job was read-only re-attested:
job state `RUNNING`, PID `3105658`, start ticks `279219396`, exact pinned
revision and command line, one advertised model alias, and GPU utilization 0%.
No new inference request was made.

## V4 pre-output refusal and V5 successor

`H3_B3_V4_PREOUTPUT_REFUSAL_2026-07-20.md` freezes the refusal at SHA-256
`9cf599b18e49d9342576f5a201a7d3312465c6a71a0ed6946b155ea9294042d7`.
At refusal, the V4 development OPEN receipt had SHA-256
`c0c42d11a9971c6f18ecaab2e7daaf25de8f8200fe9d1d80be5641dcfc8fb6f`;
its reserved inode `410701310` remained zero bytes with 0 journal events,
0 STARTs, 0 FINALIZEs, and no CLOSE. Embedding, reports, transition, and fresh
were never opened.

V5 fixes exactly the two pre-output blockers:

- extraction CLOSE schema v3 directly publishes the complete canonical
  accounting object and its SHA-256; and
- non-2xx HTTP status, headers, and raw body are durably recorded while the
  response remains non-compilable ERROR evidence.

The V5 amendment is `H3_B3_V5_RESTART_PREREG_2026-07-20.md` at SHA-256
`253ffd9e2550b30f6aa3c2d3144d4524a6f6c18ed9849f795553218e03e7eebb`.

V5 pre-freeze validation: targeted hardening suite `88 passed`; full suite
`431 passed`; `py_compile` and `git diff --check` passed. The current source
roots awaiting V5 preflight are:

- implementation root:
  `90be4a590126b08bea78dc58101c87a53b18acf2eb35892c3088f0114892cd90`;
- complete execution-source root:
  `e21407aa0d45fd9875a69354122b628461dec31d729bdd33c416280fd87f0525`;
- frozen three-gate source root:
  `2218428e2767689ebd538d99aad54031c8dcefdfc2913b43ed5e843f3513ddf5`.

## V5 execution and efficacy closeout

V5 preflight passed 9/9 and the first-write manifest was frozen at SHA-256
`9e323caa20cdcedcdb7d400889801a59dd0b0603a8ccb8eb161f2da326d6f144`.

The development extraction ran exactly once over 3,599 sources and closed at
JSONL SHA-256
`7cb1dcf65548ac9aeace33277478e0cda0dc540cfc0ae77933921a1e06899192`.
Accounting was 3,599 START, 3,599 FINALIZE, 3,599 endpoint calls, zero ERROR,
zero retry, zero unmatched START, and zero attempt-cap terminal.  The guarded
BGE-M3 bundle then closed with 3,999 x 1,024 vectors at NPZ SHA-256
`f0410cd2637233a04c126088d9772b35cd8278a0900ff025379832676956d291`.
The complete extraction-plus-embedding lineage reloaded successfully.

Both frozen development certificates refused.  On MuSiQue and 2Wiki alike,
B3 K2 minus matched B3 K1 was exactly `0.0` for nDCG@10 and ASR@10, with CI
`[0, 0]`, bit-identical score digests, and zero depth-two first-gold queries.
Both safety gates passed.  The development report is SHA-256
`8cc7b3b04295ceee26f210dc15201d325e258a4f415a1d1a09a2c5381f748896`.

The durable efficacy receipt is
`H3_B3_V5_DEVELOPMENT_REFUSAL_2026-07-20.md`.  No certificate transition was
written; fresh remains absent and unauthorized.  V5 is closed and must not be
tuned or rerun.

## Valid next sequence

1. Preserve V5 and its sealed fresh holdout unchanged.
2. Use development evidence only to diagnose the exact K2/K1 identity:
   compiler graph sparsity, claim-continuity reachability, and query-
   compatibility gating are the three preregistration candidates.
3. If a concrete mechanism defect is found, freeze a new successor protocol
   before changing extractor, ontology, compiler, or traversal behavior.
4. Do not claim demonstrated two-hop relational-composition intelligence from
   the current B3 system.  Continue to describe the verified system as an
   evidence-preserving World Compiler with certified fail-closed readouts.
