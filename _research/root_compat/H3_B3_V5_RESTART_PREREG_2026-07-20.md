# H3-B3 V5 restart preregistration — 2026-07-20

## 1. Scope and inherited claim boundary

V5 is the successor to the pre-output V4 refusal. It tests the same narrow
claim and inherits every efficacy threshold, dataset binding, extraction
prompt/config, embedding contract, retrieval policy, safety ceiling, and fresh
gate from:

- `H3_B3_COMPOSITION_PREREG_2026-07-20.md` at SHA-256
  `338a8859a7e2eebbea9c804d75f6b8e0db09d7ddf6b91db939cb30bae9f59a31`;
- `H3_B3_V4_RESTART_PREREG_2026-07-20.md` at SHA-256
  `01f130c683d016a2f235500acae9fb3b4242e40dbe0afa2376310d938d5db9f4`;
- `H3_B3_V3_REFUSAL_2026-07-20.md` at SHA-256
  `da68371a21a54b1789779453581e2aee6fc5cc1f237b43d5dde24e78cd92f4a9`;
  and
- `H3_B3_V4_PREOUTPUT_REFUSAL_2026-07-20.md` at SHA-256
  `9cf599b18e49d9342576f5a201a7d3312465c6a71a0ed6946b155ea9294042d7`.

Even a PASS supports only “evidence-bound relational composition retrieval
intelligence.” It does not establish answer reasoning, a general reasoner, or
deployment safety.

## 2. Frozen V5 deltas

V5 changes exactly two evidence-harness behaviors.

### 2.1 Direct CLOSE accounting publication

The extraction CLOSE validation schema is
`hswm-h3-extraction-close-validation/v3`. It contains both:

- `accounting`: the complete canonical accounting object returned by the
  strict extraction artifact loader; and
- `accounting_sha256`: SHA-256 of that exact canonical object.

The CLOSE must therefore directly publish physical journal rows, START and
FINALIZE rows, paragraph attempt records, endpoint calls and their upper bound,
unmatched STARTs, attempt and terminal status counts, retry-source count,
maximum attempt ordinal, overall and per-dataset attempt-cap truncation
counts/rates, all and terminal quarantine reason counts, unique request count,
prompt/completion/total tokens, and summed/mean/max call latency.

The producer must refuse CLOSE if the embedded object and its hash disagree,
if any nonterminal ERROR remains, if an unmatched START exists, or if either
frozen truncation ceiling is exceeded.

### 2.2 Non-2xx HTTP outcome preservation

An HTTP non-2xx response is an attempt outcome, not an absent response. Before
FINALIZE, the transport must preserve a bounded evidence object containing the
HTTP status, response headers, and exact raw body. It must not parse or salvage
claims from that body. The record remains ERROR unless an already-frozen rule
explicitly permits a terminal typed quarantine. Network failures with no HTTP
response remain typed transport errors with no invented body.

This change does not increase the attempt cap, alter retry eligibility, or
change the extraction JSON schema for successful responses.

## 3. Unchanged execution contract

| parameter | frozen value |
|---|---|
| endpoint | `http://127.0.0.1:18002/v1` |
| model | `Qwen/Qwen3.6-35B-A3B-FP8` |
| revision | `95a723d08a9490559dae23d0cff1d9466213d989` |
| concurrency | `2` |
| batch size | `1` |
| timeout | `180.0` seconds |
| max output tokens | `1024` |
| max endpoint attempts per request | `2` |
| extractor prompt SHA-256 | `bebcbaf01be3d0a05c7edc4284ec18e244da951f243a124bd558b39aba34fc0c` |
| extractor config SHA-256 | `185a15214301633f3353b80636438a4e5e1744633392753201256bf37267d2c0` |
| attempt journal | `hswm-recorded-llm-attempt-journal/v1` (`START`, `FINALIZE`) |

The exact RETRY1 deployment receipt remains admissible only while its process
identity, command line, revision, and one-model advertisement remain unchanged:

`.ab_p5_cache/h3_b3/QWEN35_DEPLOYMENT_RECEIPT_V2_2026-07-20_RETRY1.json`
at SHA-256
`15d3880b211c5e21a4087caa55f008d4474323a3d220e05bb47343bcd1f1c0a6`.

## 4. Evidence chain and immutable V4 refusal

- manifest: `H3_B3_RUN_MANIFEST_V5_2026-07-20.json`;
- output prefix:
  `.ab_p5_cache/h3_b3/runs/qwen35-r3-schema-v4-20260720`;
- preflight:
  `.ab_p5_cache/h3_b3/H3_B3_PREFLIGHT_RECEIPT_V5_2026-07-20.json`;
- BGE-M3 attestation:
  `.ab_p5_cache/h3_b3/BGE_M3_ATTESTATION_V2_2026-07-20.json` at SHA-256
  `430ea4606b734d97ee8e07fe7a079ce8fcd18e77f6457a9f4cb95c3340824212`.

The V4 prefix, OPEN receipt, and zero-byte inode are historical evidence. They
must remain untouched and must never receive a CLOSE. No V3 or V4 cache row,
terminal, ERROR, request result, hard link, reflink, byte copy, or parsed value
may seed V5.

V5 reuses the exact frozen corpus bindings and preimages from V4:

| binding | path / count | frozen SHA-256 or selected ID |
|---|---|---|
| development MuSiQue segment | `.ab_p5_cache/h3_b3/musique_development_v4_segment.json` | `de481a3307d8e04f17895b6c125f06a2299a821fc9254b67066058476b0b94e2` |
| development 2Wiki segment | `.ab_p5_cache/h3_b3/2wiki_development_v4_segment.json` | `10439ba55f0741fb2a092ce1dfb1fd0643cf1d0c5f42ff81dc001519608fd9fa` |
| development extraction preimage | 3,599 records | `53d827704e530d91a7847a193735718ea9df36f8fe421feaaa61393f3193d114` |
| development embedding preimage | 3,999 records | `99e44c8fd5b7d3935ab4299e0510d620643dd82a4e0ee47a389d078d739b44f4` |
| fresh MuSiQue segment | `.ab_p5_cache/h3_b3/musique_fresh_v4_segment.json` | `214d5594e6b7437f3f7a95b1bd86656f2052c0badfe2815ccff222c3eaa545c8` |
| fresh 2Wiki segment | `.ab_p5_cache/h3_b3/2wiki_fresh_v4_segment.json` | `0b6b7f58abcce938ee4ed8e0e437d23af8b7d65399b8c8ff7075279206a01b97` |
| fresh extraction preimage | 5,449 records | `9bccc338c1d1c8738ab1ea78f6283a462a278516c96b7b9d6832902041892942` |
| fresh embedding preimage | 5,999 records | `4b744d61a571d5cee122ad031a27535c529ab4c40703bfebda9b8c5a446a23bd` |

Development sidecars and fresh holdout manifests retain their exact V4 paths,
file hashes, selected IDs, and disjointness receipts.

## 5. Run and refusal rules

1. Freeze and pass a new nine-gate preflight over the final V5 code root.
2. Revalidate the exact live RETRY1 Qwen35 process.
3. First-write the V5 manifest before any V5 output.
4. Under a new lease, OPEN a new empty development extraction inode and verify
   exactly zero cache rows/hits.
5. Run all 3,599 sources once. If and only if ERROR terminals exist, rerun the
   identical full command once; the cache may call only those ERROR requests.
   A third invocation is forbidden.
6. Strict-load the journal, enforce all attempt and safety ceilings, publish the
   complete accounting object in CLOSE, and reload the CLOSE lineage.
7. Separately OPEN, produce, validate, and CLOSE development embeddings.
8. Run both development certificates only. Any refusal stops the run without a
   transition; fresh remains illegal until both pass and a transition receipt
   is frozen.

The frozen truncation ceilings remain overall rate `<= 0.005` and each dataset
rate `<= 0.01`. No efficacy threshold, retrieval policy, model, corpus,
embedding configuration, retry count, or fresh decision changes in V5.
