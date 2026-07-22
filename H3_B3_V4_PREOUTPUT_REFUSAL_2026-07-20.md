# H3-B3 V4 pre-output refusal — 2026-07-20

## Verdict

V4 is refused before its first endpoint call. Preserve its manifest,
preflight, OPEN receipt, and empty reserved extraction inode exactly. Never
append a `START`, never create its extraction CLOSE, and never reuse its output
prefix for a successor run.

This is a harness refusal, not an H3-B3 efficacy result.

## Frozen evidence

- protocol: `H3_B3_V4_RESTART_PREREG_2026-07-20.md`, SHA-256
  `01f130c683d016a2f235500acae9fb3b4242e40dbe0afa2376310d938d5db9f4`;
- preflight: 9/9 PASS, file SHA-256
  `d027f1e82a5c5065955f873796cbea4c6ba548a960c7cf782ec52edce16c571c`;
- manifest: `H3_B3_RUN_MANIFEST_V4_2026-07-20.json`, SHA-256
  `aca82aa77e81c15815562e4473ee4daae70778bba6e205cd78e5193a7c6a483c`;
- output prefix:
  `.ab_p5_cache/h3_b3/runs/qwen35-r2-schema-v4-20260720`;
- development extraction OPEN receipt SHA-256
  `c0c42d11a9971c6f18ecaab2e7daaf25de8f8200fe9d1d80be5641dcfc8fb6f`;
- reserved extraction inode `410701310`, byte count `0` at refusal;
- journal events `0`, durable STARTs `0`, FINALIZEs `0`, records `0`;
- endpoint calls `0`; extraction CLOSE absent; embedding OPEN/CLOSE absent;
  development report and transition absent; fresh entirely unopened.

The OPEN receipt correctly binds the V4 manifest, protocol, code root,
preflight, input, extractor config, deployment receipt, producer code, and the
empty inode. It remains valid historical evidence even though production was
refused.

## Why the harness refused

### R1 — detailed CLOSE accounting was committed but not published

V4 preregistration section 5 requires the extraction CLOSE accounting to
publish the physical attempt rows, endpoint calls, status and retry counts,
maximum ordinal, truncation counts/rates by dataset, quarantine reasons,
tokens, and latency totals.

`extraction_close_validation()` exposed only `accounting_sha256`, not the
canonical accounting object. A later development report would expose the
values only after the embedding stage succeeded. That is neither the
extraction CLOSE itself nor durable reporting under an intermediate failure.
The hash is a commitment, but it is not publication of the mandated values.

### R2 — non-2xx HTTP response bodies were not evidence-preserving

The V4 transport read an `HTTPError` body and then raised the exception. The
outer error adapter consequently journaled an empty `raw_response` and only an
exception type. If a later retry succeeded, the first non-2xx raw outcome body
would be missing even though V4 section 3.1 requires full raw attempt outcomes.

Neither gap is allowed to be repaired after the V4 manifest froze its code
hashes. Production therefore stopped before the first durable START.

## Successor requirements

A successor must:

1. place the full canonical extraction accounting object and its SHA-256 in
   the extraction CLOSE validation;
2. preserve a bounded non-2xx HTTP outcome, including status, headers, and raw
   body, in the durable FINALIZE evidence without compiling or salvaging it;
3. add regressions for direct accounting publication, accounting tamper
   rejection, HTTP-error body preservation, and bounded retry behavior;
4. create a new preflight, manifest, output prefix, OPEN receipt, and empty
   inode; and
5. retain every V4 threshold, model, input, token cap, attempt cap, and fresh
   gate unchanged unless an explicit successor preregistration says otherwise.

