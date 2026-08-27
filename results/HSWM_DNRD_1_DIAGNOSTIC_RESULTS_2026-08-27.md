# HSWM-DNRD-1 diagnostic result: VOID_PROTOCOL

- Date: 2026-08-27
- Experiment: `HSWM-DNRD-1`
- Frozen family: `REPEATED_CONTEXT_TABULAR_ROUTING_MECHANICS_V1`
- Authoritative terminal: `VOID_PROTOCOL`
- Scientific status: `UNJUDGED`
- Calls completed before termination: `1`
- Retry, resume, replacement, or second pulse: forbidden

## Result first

The sole preregistered occurrence did not measure the proposed durable routing
mechanics. The frozen deployment preflight succeeded, but the first training
chat completion was rejected by the frozen response contract. The runner
retained a post-first-call inconclusive record. The executor then failed while
constructing the mandatory bundle index, so the frozen adjudicator returned
`VOID_PROTOCOL` rather than `INCONCLUSIVE_OCCURRENCE`.

This is a material negative instrument result. It establishes no routing
persistence, rollback, derangement sensitivity, replay fidelity, LLM learning,
utility, efficacy, or HSWM continuous learning.

## Canonical role and conceptual delta

HSWM's target identity remains the single token-native LLM-function
macro-neural network in which the evolving hypergraph is simultaneously the
living harness, world model, and continuous learner. DNRD-1 was only a bounded
schema-approved projection of a durable integer routing seam. It was never a
separate cognition subsystem or an HSWM efficacy test.

The intended delta over the prior P1 RED result was narrow: test whether an
outcome-bound integer routing payload could persist across fresh-process
recovery and actuate repeated-context pre-model routing under exact rollback,
derangement, and fixed-rule replay controls. Because the occurrence stopped on
the first training response, none of those mechanics checks ran.

## Frozen identity and chronology

| Binding | Exact value |
|---|---|
| Source A | `6f240077b8ce7395da5aea94f5c68ad888c8a740` |
| Source A tree | `df4affe643e5eecf13675a43f8683acf57f64ed0` |
| Source manifest SHA-256 | `795222551e71a9577fa33f1fa0235b11d2e515078a088a5502373d8d46b4ae41` |
| Direct-child preregistration B | `0e79353521f2927a74d974b274560d7acc4acd0a` |
| Preregistration SHA-256 | `a72e5730126f6fb79cc417316706b149625bdaa8daed4ecb6a870944e00e9a94` |
| Ratification statement SHA-256 | `0dce76113e8b8a1732201f9d61e8e24f45b7fde832c7b2d665dd2494ad5a1b96` |
| Ratification time | `1787844155` |
| First eligible Quicknet round | `31680564` |
| Round time | `1787845056` |
| Pulse binding self-receipt | `8ede2f241316d3843317c2bb3d949cf55c5901ccc6f0cfdd8dc3a1e05a687d88` |
| Attempt marker self-receipt | `54b9952efcf071d5994194aef2e74dd6170cc48cc4282a2e77eeef6d0e7d93b0` |

The user supplied the correct preregistration hash and ratification template
twice with display line wrapping. The external ratification receipt records the
operator interpretation explicitly as
`USER_EXPLICIT_RATIFICATION_INTENT_CANONICAL_TEMPLATE_WHITESPACE_NORMALIZED`;
it does not claim byte-exact attestation of the displayed multiline message.

The exact eligible Quicknet pulse was verified online with the pinned Node and
`drand-client` closure. The durable attempt marker was created before the live
boundary, as preregistered. It remains present and consumes this occurrence.

## Observed execution

The frozen three-call non-generation preflight succeeded:

- served model `qwen3.6-35b-a3b`;
- root `Qwen/Qwen3.6-35B-A3B-FP8`;
- maximum model length `32768`;
- vLLM `0.25.1`;
- exactly `3` non-generation HTTP calls and `0` generation calls in the
  deployment receipt; and
- tokenizer count `10` for the separately frozen preflight prompt.

The first training request then produced one HTTP `200` response in
`452701679` nanoseconds. The model ledger contains exactly one
`CHAT_COMPLETION_OBSERVED` event and no `CHAT_COMPLETION_ACCEPTED` event. The
runner ledger is empty. The retained inconclusive record states:

- `post_first_call=true`;
- `calls_completed=1`;
- `client_cache_hits=0`;
- `failure_type=LiveBoundaryError`; and
- failure digest
  `6067deda71eee8928d38c63602aee69fa45df01a39375786e3084ba0f7a3dca0`.

Exhaustive comparison against the finite frozen `LiveBoundaryError` messages
reconstructs that digest uniquely as:

> chat completion choice must finish with exact reason 'stop'

The parser order additionally establishes that the response was a UTF-8 JSON
object, reported the frozen model ID, and contained exactly one object choice.
Its `finish_reason` was not `stop`. The actual finish reason, response content,
and usage fields are unknown because the failure event retained only the raw
response SHA-256
`3d1fe7b8e5e217a0fb1881c7c84896d5639326a028f9617016cb69634fcf2e27`,
not the bounded raw response body.

The required selected-evidence response token for that request was 26 ASCII
characters and the constructed request prompt was 352 characters.
`max_tokens` was 16. A
length-limited completion is therefore a plausible explanation, but it is not
established by the retained evidence. The generic preflight tokenized neither
the actual task prompt nor the required output-token family.

## Deterministic bundle-seal failure

After writing `inconclusive.json`, the frozen executor attempted to enumerate
the evidence bundle. It sorted `Path` objects and then required the serialized
relative POSIX strings to be lexicographically sorted. Those orders differ when
a sibling file and directory share a prefix. The first observed inversion was:

```text
bridge_runtime_closure/node_modules/@types/node/assert/strict.d.ts
bridge_runtime_closure/node_modules/@types/node/assert.d.ts
```

Component-wise `Path` ordering places the `assert/` directory before the
`assert.d.ts` file, while serialized byte ordering places `assert.d.ts` before
`assert/strict.d.ts`. The executor therefore exited `2` with:

```text
DNRD execution refused: bundle index artifact paths are not canonical
```

The failure is deterministic for the selected 4,050-file runtime closure. The
test fixture lacked a `foo.ext` versus `foo/child` prefix collision and checked
the index schema but not producer ordering followed by adjudicator admission.

No `bundle_index.json` was written. A forensic, non-authoritative commitment
over the incomplete external tree covers 4,115 regular files, 443 directories,
and 58,009,294 file bytes. Its canonical file-row commitment is
`30b3a8292898f2aea093a6c55bb73e884635bde21189c97af959f6c71f323c39`.
This commitment records the failed tree; it is not a replacement bundle index.

## Independent adjudication

The frozen Source-A judge was run against the directory bundle. The same judge
copied into the occurrence source closure was also run with the pinned Python
runtime and returned the identical judgment:

- terminal: `VOID_PROTOCOL`;
- failure reason: `bundle is missing required artifact 'bundle_index.json'`;
- bundle verification receipt:
  `9883e5c369794ade37a61ece70f73eebc67d16647dd20ea3e39bba527f5ffb86`;
- raw canonical judgment SHA-256:
  `76e332426f0bd6d9955cddfd18fa386df7b62b416396b0212ae90c6270ca0465`;
- scientific status: `UNJUDGED`;
- efficacy: `NOT_EVALUATED`; and
- learning and canonical Permit: `NOT_ESTABLISHED`.

The raw frozen judgment also contains the generic claim-boundary literal “An
indexed post-first-call inconclusive occurrence was retained” and the generic
authority label `AUTHORITATIVE_EVIDENCE_BUNDLE_VERIFIED`. Those literals are
mechanically emitted by the judge's VOID branch and do not describe successful
bundle admission here. The same judgment's failure reason, the absent index,
and terminal control the interpretation: an `inconclusive.json` record was
retained, but it was not indexed or admitted as a complete bundle.

Had the mandatory index been sealed and validated, the runner-level record
could have reached the `INCONCLUSIVE_OCCURRENCE` adjudication branch. That
counterfactual did not occur. The authoritative terminal for the actual bytes
is `VOID_PROTOCOL`.

## Scientific interpretation

The occurrence falsifies readiness of the DNRD-1 measurement instrument under
its selected production closure. It does not falsify or support the proposed
durable routing mechanics because no scorer outcome, routing update, repeated-
context evaluation, recovery, rollback, derangement, or replay comparison was
completed.

The result also answers the harness-versus-science concern directly: source
closure and 206 focused tests were insufficient evidence of experimental
readiness. The first live attempt exposed both an unmeasured model-response
contract risk and a deterministic evidence-sealing defect. Tests remain
evidence instruments; their growth is not scientific progress by itself.

## Required successor gate

HSWM-DNRD-1 is closed. The existing marker and preregistration forbid retry,
resume, replacement, a second pulse, or hand-adding the missing bundle index.
A successor must be a separately frozen and ratified experiment, such as
HSWM-DNRD-2, and must at minimum:

1. sort bundle-index entries by their serialized relative POSIX path and add a
   `foo.ext` versus `foo/child` regression plus producer-to-judge end-to-end
   coverage over the real closure shape;
2. retain bounded raw HTTP response bytes privately on parser failure, together
   with an exact parser-stage code, so a failure is forensically identifiable;
3. predeclare an output-token budget check over the actual diagnostic token
   family and preserve headroom rather than relying on an unrelated tokenizer
   prompt; and
4. prove the complete evidence-sealing path before consuming a live singleton
   marker.

Only after those instrument gates pass may a new preregistration ask the same
narrow mechanics question. Even a future mechanics GO would remain below LLM
learning, unseen-context generalization, utility, and HSWM efficacy.

## Artifacts

- Raw judgment: [`dnrd_1_judgment_2026-08-27.json`](raw/dnrd_1_judgment_2026-08-27.json)
- Evidence receipt: [`EVIDENCE_HSWM_DNRD_1_ADJUDICATION_2026-08-27.json`](../evidence/EVIDENCE_HSWM_DNRD_1_ADJUDICATION_2026-08-27.json)
- External failed occurrence:
  `/home/lagyeongjun/.local/share/hswm/dnrd/HSWM-DNRD-1/occurrence-1-evidence`
