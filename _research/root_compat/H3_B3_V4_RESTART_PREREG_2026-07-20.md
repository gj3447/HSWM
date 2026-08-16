# H3-B3 V4 operational restart preregistration — 2026-07-20

Status: frozen before any V4 producer output or efficacy metric.

## 1. Scope and inherited protocol

This is a narrow operational amendment to
`H3_B3_COMPOSITION_PREREG_2026-07-20.md` at SHA-256
`338a8859a7e2eebbea9c804d75f6b8e0db09d7ddf6b91db939cb30bae9f59a31`.
All datasets, splits, retrieval arms, causal nulls, statistical tests, margins,
and development-to-fresh transition rules remain unchanged.

V3 was refused before efficacy because two of 3,599 development sources
remained `finish_reason=length` after the sole identical retry.  Its immutable
receipt is `H3_B3_V3_REFUSAL_2026-07-20.md` at SHA-256
`da68371a21a54b1789779453581e2aee6fc5cc1f237b43d5dde24e78cd92f4a9`;
its extraction JSONL SHA-256 is
`bab9d5bb4d152c3f65e15f5fb2f876c37846fbb09aa101442c7b87f7ca54ef1b`.
No V3 retrieval score was opened.

## 2. Frozen V4 extraction execution

| field | frozen value |
|---|---|
| schema | `hswm-recorded-llm-extractor/v4` |
| endpoint | `http://127.0.0.1:18002/v1` |
| model | `Qwen/Qwen3.6-35B-A3B-FP8` |
| revision | `95a723d08a9490559dae23d0cff1d9466213d989` |
| batch size | `1` |
| max concurrency | `2` |
| timeout | `180.0s` |
| max output tokens | `1024` |
| max endpoint attempts per request | `2` |
| decoding | temperature `0`, top-p `1.0`, seed `0`, thinking disabled |
| prompt SHA-256 | `bebcbaf01be3d0a05c7edc4284ec18e244da951f243a124bd558b39aba34fc0c` |
| config SHA-256 | `185a15214301633f3353b80636438a4e5e1744633392753201256bf37267d2c0` |

Concurrency, timeout, and attempt cap are part of the config preimage and
therefore change both config SHA and request identity.  Authentication is not
part of the scientific preimage.

The 1024-token cap is an operational repair, not performance tuning.  V3's two
unresolved sources stopped exactly at 512 twice with identical response-content
hashes.  Among non-length V3 attempts, nearest-rank p99 was 403 and the maximum
was 507 completion tokens.  1024 is the smallest predeclared power-of-two cap
above twice the prior cap; 2048 is not used.

## 3. Attempt state machine

| endpoint result | before attempt cap | at attempt cap |
|---|---|---|
| exact `stop`, exact model, valid envelope | existing SUCCESS / PARTIAL / QUARANTINED compiler path | same |
| exact model and otherwise valid envelope with `finish_reason=length` | ERROR; one identical retry permitted | raw content is not parsed or salvaged; freeze canonical empty claims plus `truncated_response_at_attempt_cap`; terminal QUARANTINED |
| transport failure | ERROR | ERROR; no further endpoint call; CLOSE forbidden |
| model mismatch | ERROR | ERROR; no further endpoint call; CLOSE forbidden |
| other invalid envelope / content filter | ERROR | ERROR; no further endpoint call; CLOSE forbidden |

Attempt rows are append-only, contiguous, and ordinal `1..N` with `N<=2`.
There must be exactly one compiler-admissible terminal row per source, and it
must be that source's last attempt.  Every attempt, including ERROR rows, must
match the manifest's model revision, prompt SHA, and config SHA.

### 3.1 Durable attempt intent

Every endpoint attempt has a durable START intent.  Under the extraction
artifact's exclusive lease and file lock, the producer must append a canonical
`START` journal event containing the exact attempt identity, source membership,
request SHA, prompt SHA, config SHA, and attempt cap to the same extraction
JSONL.  The OPEN phase has already created, fsynced, and published that inode;
each START must flush and call `fsync` on the existing file **before** issuing
the HTTP request.  A directory fsync is additionally required only if a file or
directory entry is created, not for every append.  Only after the START file
fsync may the endpoint-call counter advance and the request leave the host.
After the call, one canonical `FINALIZE` event must join the START by start ID,
attempt ID, ordinal, batch identity, and the full raw outcome records.

A START without FINALIZE is an interrupted call with unknown external
completion.  It permanently consumes that ordinal, is never a cache hit or
compiler-admissible terminal, and blocks extraction CLOSE.  A later invocation
may only use the next ordinal if one remains; it cannot replay or overwrite the
unmatched ordinal.  FINALIZE without its exact preceding durable START, a
duplicate START/FINALIZE, or a mismatched join is artifact corruption.  This
ordering is mandatory for attempt 1 and attempt 2, including transport
failures.  The journal schema is
`hswm-recorded-llm-attempt-journal/v1`; event types are exactly `START` and
`FINALIZE`.

The OPEN receipt, journaled extraction JSONL, and CLOSE accounting must share
one manifest/run identity.  An ordinary retry may consume only the immediately
preceding finalized V4 ERROR for the same request identity.  A next-ordinal
recovery attempt after an unmatched START is exceptional and cannot lift that
START's CLOSE block.  No V3 row, V3 request outcome, or V3 cache state can
satisfy a V4 START or FINALIZE.

## 4. New evidence chain

- manifest: `H3_B3_RUN_MANIFEST_V4_2026-07-20.json`
- output prefix:
  `.ab_p5_cache/h3_b3/runs/qwen35-r2-schema-v4-20260720`
- preflight:
  `.ab_p5_cache/h3_b3/H3_B3_PREFLIGHT_RECEIPT_V4_2026-07-20.json`
- frozen three-file preflight gate-source code root:
  `2218428e2767689ebd538d99aad54031c8dcefdfc2913b43ed5e843f3513ddf5`
- Qwen35 deployment receipt:
  `.ab_p5_cache/h3_b3/QWEN35_DEPLOYMENT_RECEIPT_V2_2026-07-20_RETRY1.json`
  at SHA-256
  `15d3880b211c5e21a4087caa55f008d4474323a3d220e05bb47343bcd1f1c0a6`
- development extraction input: the existing 3,599-row v4 input at SHA-256
  `53d827704e530d91a7847a193735718ea9df36f8fe421feaaa61393f3193d114`

All corpus bindings below are inherited evidence, not values the V4 manifest
builder may recompute and silently replace:

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

Development evaluator sidecars are frozen as
`.ab_p5_cache/h3_relation_raw_musique.json` at
`c44453d2534cd326000f65dfa7d3f02b879f4390cd0fbc067617ad84e0a6bd9e`
and `.ab_p5_cache/h3_relation_raw_2wiki.json` at
`212c43c5116d114e73d0b02e5fcd28580043ae306d3303fea0d76276715047ed`.
Fresh holdouts are frozen as
`.ab_p5_cache/h3_b3/musique_fresh_manifest_v2.json` at file SHA-256
`12bffedbce50be64019727f3a39309af0676e76ce3ef30e74bcb38932bea991c`
with selected ID
`8aafec838c80d136ebea0dc8f084b7a3a088027f3876fa5ffab63ff1f7851537`,
and `.ab_p5_cache/h3_b3/2wiki_fresh_manifest_v2.json` at file SHA-256
`2c1bed2236b0127209cae5f009dacfe41c03a2b38c401f993cb8f3aab1edc343`
with selected ID
`4b0f41685aabb62cabf67497baf0a31776c3c9bd5195bef801dc9ae047998b47`.

The V4 OPEN receipt must reserve a new empty inode.  All 3,599 development
sources are rerun.  No V3 terminal or ERROR row may be copied, linked, or used
as a V4 cache hit.  The V4 journaled extraction JSONL must be a newly created
empty artifact: hard links, reflinks, byte copies, parsed salvage,
request-result import, or cache seeding from V3 are forbidden.  The first V4
development invocation must therefore report exactly zero cache hits before
making its first endpoint call.  Fresh outputs remain unopened.

## 5. Mandatory safety reporting and ceilings

The extraction CLOSE accounting must publish:

- physical attempt rows and endpoint calls;
- status counts and retry-source count;
- maximum attempt ordinal;
- total `truncated_response_at_attempt_cap` sources and overall rate;
- that count and rate separately for MuSiQue and 2Wiki;
- all quote-quarantine reason counts; and
- prompt/completion/total token and latency totals.

The extraction is refused if any nonterminal ERROR remains.  It is also refused
if attempt-cap truncation exceeds either frozen ceiling:

- overall rate `> 0.005`; or
- either dataset's rate `> 0.01`.

These are safety ceilings, not efficacy targets.  Their counts and rates are
reported even when zero.

## 6. Phase gates

1. Finish code and tests; create a new nine-gate preflight bound to the new code
   root.
2. Validate the exact frozen RETRY1 Qwen35 receipt against the live deployment.
   A changed process identity invalidates this V4 preregistration and requires
   a successor preregistration; an alternate self-consistent receipt is not
   admissible in this run.
3. First-write the V4 manifest before any V4 output.
4. Lease-only OPEN, produce, domain-validate, and CLOSE the full development
   extraction.
5. Separately OPEN, produce, validate, and CLOSE development BGE-M3 embeddings.
6. Run development certificates for both datasets only.
7. If either refuses, stop without a transition.  Fresh production is legal
   only after both pass and the transition receipt is frozen.

No threshold, retry count, token cap, extraction rule, retrieval policy, or
fresh decision may be changed after the V4 manifest is published.
