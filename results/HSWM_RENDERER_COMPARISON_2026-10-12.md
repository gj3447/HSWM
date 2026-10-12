# HSWM renderer comparison — 2026-10-12

## Result

DGX run `renderer-e1-20261012T052306Z` tested the frozen 32-case historical,
development-exposed oracle cohort. It compared the historical JSON bridge
presentation (`legacy`) with an ordered role/context/exception presentation
(`ordered`). Both arms used the same oracle relation text, model configuration,
strict E1 schema, and evaluator. The run completed **64/64 valid** outputs.

| arm | environmental correct | family counts | total tokens | summed request latency |
|---|---:|---|---:|---:|
| legacy | 17/32 | [4, 4, 6, 3] | 8,962 | 14,179.568450 ms |
| ordered | 14/32 | [3, 3, 4, 4] | 8,264 | 14,415.994393 ms |

Paired outcomes were 11 both-correct, 6 legacy-only, 3 ordered-only, and 12
both-wrong. The predeclared result is **`REVISE_LOCAL_EXECUTION`**. The ordered
renderer is not adopted from this screen; the next token/mode comparison is
`NOT_RUN`.

## Execution identity

- Time: 2026-10-12 05:30:39.912282–05:31:15.364946 UTC; wrapper interval
  05:30:34–05:31:15 UTC.
- Served identifier: `qwen3-4b-real`; temperature 0, seed 0, max tokens 32,
  non-thinking, strict E1 JSON.
- Family order: 0/2 legacy first; 1/3 ordered first. This is family-level
  counterbalancing only, not randomized per-case order.
- Before execution, all 32 legacy requests were checked byte-identical to the
  prior oracle request rendering.
- Receipt archive SHA-256:
  `3f90fbf1916f166da9d6301662f1dc8dab34fd599d1bfd6b3d8e88c1a2e4c617`.

An independent audit completed with `PASS`: it read 34 input files, 8 raw
Inspect logs, and all 64 request/response pairs; it independently recomputed the
finite target scores, token totals, latency sums, and family order, obtaining the
same 17/32 and 14/32 result. Private inputs, raw Inspect logs, and
request/response records remain under ignored `.hswm-local/` material. No host
address is recorded here.

The planned observed graph projection is documented in
[`HSWM_LIKENESS/docs/LOCAL_EXECUTOR_EXPERIMENT_2026-10-12.md`](../../HSWM_LIKENESS/docs/LOCAL_EXECUTOR_EXPERIMENT_2026-10-12.md).
Its graph validation status is not claimed in this report.

## Boundary

This is a development diagnostic on old exposed cases, not a holdout or a
statistical generalization claim. It does not establish why either renderer
failed, W learning, a canonical graph-program revision, interpreter efficacy,
or general HSWM efficacy. The canonical graph program and its versioned
interpreter remain separate: no canonical state or interpreter source changed.

HSWM_LIKENESS contains the standard research graph, USL bindings, and
SHACL/SPARQL plans for provenance and proposed experiments. Those projections
are not canonical HSWM writes and do not turn a valid output or structural
validation into semantic truth. A fresh family-disjoint final cohort is required
before any selection claim.
