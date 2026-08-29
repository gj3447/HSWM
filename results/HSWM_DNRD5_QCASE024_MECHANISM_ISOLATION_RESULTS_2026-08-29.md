# HSWM-DNRD-5 QCASE-024 mechanism-isolation v4 result

- Date: `2026-08-29`
- Machine: DGX execution host `edgexpert-e229`
- Served model: `qwen3.6-35b-a3b`
  (`Qwen/Qwen3.6-35B-A3B-FP8`, revision
  `95a723d08a9490559dae23d0cff1d9466213d989`)
- Runtime: vLLM `0.25.1`, NVIDIA GB10, compute capability `12.1`
- Frozen terminal: `LIVE_COMPLETE_DGX_QCASE024_MECHANISM_DIAGNOSTIC`
- Frozen observation pattern: `BOTH_ARMS_VARIATION`
- DNRD-5 causal effect: `NOT_EVALUATED`
- Source-A disposition: `SOURCE_A_REFUSED_EXACTNESS_UNQUALIFIED`
- Retry, resume, replacement, or reuse of this plan: forbidden

## Result first

The post-result-selected `QCASE-024` mechanism diagnostic completed its frozen
2×2 ABBA design: 16/16 serial POSTs succeeded with zero retry, four distinct
fresh-server identities were verified, and a separately executed frozen
verifier independently reconstructed the same terminal and reductions.

Each four-call block had byte-exact assistant-content UTF-8 internally. Across
fresh launches, however, both `ASYNC_ENABLED` and `ASYNC_DISABLED` produced the
same two distinct assistant-content values, four observations of each value per
arm. The frozen pattern is therefore `BOTH_ARMS_VARIATION`.

This directly rules out a narrow proposed remedy: disabling vLLM asynchronous
scheduling did not guarantee stable assistant-content bytes across the two
observed fresh disabled blocks. It does **not** establish that async scheduling
has zero effect, nor does it attribute the variation to launch order, Gated
DeltaNet, FP8, a kernel, a reduction path, or any provider-internal mechanism.

## Direct measurement

| Item | Result | Interpretation |
|---|---:|---|
| Frozen budget | 4 blocks × 4 serial calls = 16 POSTs | Fully consumed; no rerun |
| START / successful TERMINAL | 16 / 16 | HTTP success; retry 0 |
| Fresh server identities | 4 distinct | One new container/process/cache boundary per block |
| Exact blocks | 4 / 4 | Each block had content cardinality 1 and modal count 4 |
| Async-enabled arm cardinality / mode | 2 / 4 | Two content values, four occurrences each |
| Async-disabled arm cardinality / mode | 2 / 4 | The same two content values, four occurrences each |
| Global cardinality / mode | 2 / 8 | Two values, eight occurrences each |
| Content store | 80 blobs | Manifest SHA-256 `3b5f20e9…02c4f` |
| DNRD-5 causal blocks/calls | 0 / 0 | Causal effect remains unevaluated |

The exact block sequence was:

| Launch position | Arm / block | Four-call content | Bytes |
|---:|---|---|---:|
| 1 | `ASYNC_ENABLED/B01` | `fa0f987e…f19a22` | 194 |
| 2 | `ASYNC_DISABLED/B01` | `14bc62d6…262a31` | 234 |
| 3 | `ASYNC_DISABLED/B02` | `fa0f987e…f19a22` | 194 |
| 4 | `ASYNC_ENABLED/B02` | `14bc62d6…262a31` | 234 |

Thus arm-wise marginal counts were identical, while the four observed block
values separated perfectly by launch-position parity: positions 1 and 3 had
the 194-byte value, and positions 2 and 4 had the 234-byte value. This is a
descriptive four-block association, not evidence that parity or time caused the
branch. The experimental unit for a between-launch mechanism is the fresh
block, not the four repeated requests within it; treating all 16 calls as
independent block evidence would be pseudoreplication.

## The two exact outputs

The 194-byte value was:

```json
{
  "answer": "VISTA",
  "rationale": "The first cue indicates that the word begins with the letter V. The second cue is irrelevant to the selection as it describes a different word entirely."
}
```

Its SHA-256 is
`fa0f987e4b75e216b5522929f6722f285e9026d00a42fe92a269f72d1ef19a22`;
the exact bytes are preserved in the
[`194-byte assistant content`](raw/dnrd5_qcase024_mi_1_content_v4_194_byte_assistant_content_2026-08-29.json).

The 234-byte value was:

```json
{
  "answer": "VISTA",
  "rationale": "The first cue explicitly starts with the letter V, which matches the beginning of VISTA. The second cue describes the word WATER, which is a different label and does not fit the initial letter"
}
```

Its SHA-256 is
`14bc62d62791f445e539a4c4e1f212c0d7e5d818095ae87608fcc8eabf262a31`.
These are the same bytes already preserved as the Q1 modal
[`assistant content`](raw/dnrd5_dgx_live_q1_qcase024_modal_assistant_content_2026-08-29.json),
so no duplicate content file was created.

Both outputs retained the answer field `VISTA`, but their rationale UTF-8
bytes, wording, and lengths differ. Answer-field stability is a descriptive
observation made after selection; correctness and semantic-equivalence
endpoints were not registered and were not evaluated.

## First divergence and processed-logprob evidence

The independent verifier located the first differing UTF-8 byte at offset 53.
Both sides were aligned to completion-token index 20, whose leading-space token
span began at byte 52:

| Output | Selected token | Selected log probability | Gap to best nonselected | Other output's token rank / gap |
|---|---|---:|---:|---:|
| 194-byte | ` indicates` | `-1.7900172472000122` | `0.2499998807907105` | rank 1 / `0.2499998807907105` |
| 234-byte | ` explicitly` | `-2.0457708835601807` | `0.125` | rank 4 / `0.375` |

All candidate identities, emitted bytes, and exact decimal strings were
retained in the content-addressed traces. These values show that the branch was
visible at the token-score surface. No near-tie threshold was preregistered, so
the gaps are descriptive and do not identify the source of the score change.

## Frozen execution and independent verification

The v4 source identity is commit
`6ff34761bfdba107a8d3c765e42b9aa5b5efd091`, tree
`ac362fdf1e1321333b5c52b0bb2fbae3951e2080`. First-attempt source CI run
[`33269283082`](https://github.com/gj3447/HSWM/actions/runs/33269283082)
completed all eight jobs successfully; its strict receipt SHA-256 is
`ff1d2610032892a0f9d2648152216acd379df9d9120158b524fb48db51aa7160`.

The publication identity is commit
`2ca0fb20833103bbe1331e1dabc2ae02ffee4878`, tree
`6ce1b9fac404ec5940fb1356c2172361d1fdf77d`. First-attempt publication CI run
[`33269801645`](https://github.com/gj3447/HSWM/actions/runs/33269801645)
also completed all eight jobs successfully; its strict receipt SHA-256 is
`ad9e8d1e2d735186821ec3d78a7b94904b58f14bd6499536ad7437ef39805c49`.

The immutable freeze binds plan SHA-256
`c5aea1a4f57129a23c6e1f72b7b328f35295f867eb186ddfc7f8fe4b94647f0f`,
start-marker SHA-256
`5c2e9496bbfcacfa9fcd5b67de282548281f5324effc6865f155114760844c8a`,
closure-manifest SHA-256
`4dbb80077b2e83c96c6e307df0d0e1816c9285baaceb259f5330f0f58c1c547a`,
root-genesis SHA-256
`70a5a60aebd9ff406c91673c97df4d7d5b3a2b1ae23e39d8dc07e4ffa20dbebd`,
and frozen verifier-build SHA-256
`fa9d8e498c95222f2b812aadacfde4990abac42099faed437696b25066d11ee7`.
That build binds frozen verifier-source SHA-256
`91f1069e516a35807600003058e294944759bbbfbc9827df2ce35184260a1487`.

Live run `dgx-qcase024-mi-1-v4-live-2ca0fb2-002` ran from
`2026-08-29T19:27:39Z` through `20:01:39Z`. Its wrapper receipt SHA-256 is
`a3d3cd4d804867ba17eb6674356eeec627a71dd7bbc0c3b0d34a3eff875e32e7`;
the 2,099,200-byte archive SHA-256 is
`3192f6c808d07501eef2531fe0c2c4d5137e0045096a64f4d571f95bcb428589`.
The one-time consumption marker SHA-256 is
`0a87322cdcfd41c18f521e83f433a70c8fa466cd7985e5f9df9fe00fd011fadb`.

The exact 39-row ledger SHA-256 is
`838f338946af641f69e0e234eafbe8589be9c783dbc12870e1d110128c8a160b`;
its final chain record is
`1d11b1f451c78f6bc8adbd2c0cc411d3e35420d795909a92446d9e3adcfc24a2`.
The checked-in exact ledger, live wrapper receipt, frozen-verifier output, and
verifier wrapper receipt are available in [`raw`](raw/).

Independent run `dgx-qcase024-mi-1-v4-verify-2ca0fb2-001` used the frozen
verifier once. It reproduced the complete terminal, pattern, ledger chain,
block/arm reductions, content manifest, and eight first-divergence comparisons.
Its output SHA-256 is
`7cd98ce4ec019a25368ba9878c01508fdf30a8842754dd34c9595ee693bbb56e`,
wrapper receipt SHA-256 is
`46cf786cb734c84cd50ea6e9e8d2f3d5a8f121494b23abfa7d77d38e04693675`,
and 20,480-byte archive SHA-256 is
`4b884c97da16f0be7ba5f5c378f0983cc4521b739ccb09f4cd083574a56c8802`.
After execution, all four displaced local services returned HTTP 200 on their
declared health endpoints.

## Zero-call operational chronology

Three publication preflights made no target call and did not burn the plan.
The first failed before Python because `uv` was absent from the wrapper PATH;
the second failed before Python because remote quoting produced invalid source;
the third used the checked-in environment's `.venv/bin/python` and passed.
Their receipt SHA-256 values are, in order,
`1eed31328e7c96526672df312ac0b84837f2cfb8d3391135e8ea84f955c53b9b`,
`9578bf11147591b47e84442a1bbea380d088177cf8304501e26211b9ac7880f9`,
and `39b300e315e6e7ce81aa07bba8847972f6414f5971d08a1ec9247b0f1cbaface`.

The first live wrapper, `dgx-qcase024-mi-1-v4-live-2ca0fb2-001`, refused
before runner construction because the declared registry directory did not yet
exist. It made zero target calls and zero plan burns, then restored services.
Its receipt SHA-256 is
`54307e1c924b1e74050e236d82c74b331c735247bd2f2e9f37fb9dc0381f8866`.
After the empty mode-0700 registry was created at the already frozen path, only
the successful live run wrote the single consumption marker and all 16 STARTs.
These operational attempts are chronology, not additional scientific results,
and receive no result-log row or scientific receipt of their own.

## Advanced-model boundary

The measured boundary is a revision- and digest-pinned local open-weight
inference configuration: a 35B-total/3B-active FP8 Qwen3.6 model on NVIDIA
GB10 with the vLLM runtime image digest pinned. The
[Qwen model card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8/blob/95a723d08a9490559dae23d0cff1d9466213d989/README.md)
documents the model family; NVIDIA's
[DGX Spark hardware guide](https://docs.nvidia.com/dgx/dgx-spark/hardware.html)
supplies GB10-platform context; and the version-matched
[vLLM 0.25.1 engine-argument reference](https://docs.vllm.ai/en/v0.25.1/configuration/engine_args/)
documents the selected argument semantics. The frozen identity records—not
those vendor pages—bind the exact executed revision, image, driver, and flags.

This is not a state-of-the-art quality or throughput result. The experiment
used a 32,768-token, text-only, non-thinking path with one sequence, eager mode,
prefix cache disabled, and only 50% GPU-memory utilization to preserve the
comparison boundary. NVIDIA's 2026-08-25
[DGX Spark Founders Edition release notes](https://docs.nvidia.com/dgx/dgx-spark/release-notes.html)
list driver `580.159.03`, newer than this OEM node's frozen `580.126.09`; the
notes also say partner GB10 systems need not update on the same schedule.
Neither driver is asserted to be optimal for this exact model/runtime pair.
Changing the driver or vLLM before MI would have confounded Q1-to-MI
interpretation. vLLM `0.25.1` was retained as the frozen study runtime, not
asserted to be the latest available vLLM release or a GB10 performance optimum.
No vision, native 262,144-token context, tool use, benchmark quality, or
throughput claim was tested.

## Scientific interpretation and next experiment

The result narrows the mechanism search from within-process request history to
a between-fresh-launch boundary in this finite sample: requests were stable
within every observed process, but the selected rationale changed across
fresh processes under both async settings. This localization is useful, but it
does not identify what in that boundary mattered.

The next decisive diagnostic must treat fresh launch as the experimental unit.
It should preregister at least two balanced `EDDE`/`DEED` launch sequences so
each async arm occurs equally at odd and even launch positions, retain the
same request and identity checks, and keep within-block calls as repeatability
measurements rather than independent causal samples. A later factor study can
then alter checkpoint precision or backend separately; those interventions
must not be mixed into the launch-order study.

This MI was selected after Q1 and remains non-confirmatory. It does not estimate
a population repeatability rate, rescue Q1, qualify Source A, or evaluate a
DNRD-5 causal effect.

## HSWM and FCL boundary

HSWM remains one token-native LLM-function macro-neural network whose evolving
hypergraph jointly plays living-harness, world-model, and continuous-learner
roles. This experiment, its repository files, the ontology, and the live KG are
bounded evidence projections and interfaces, not HSWM cognition or learning.

The result does not test or change any of the eight FCL laws, same-rule
recursive HSWM-of-HSWMs composition, outcome-bound causal learning,
consciousness, selfhood, or scale-invariant causal closure. The scientific
status remains
`SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`; therefore the live KG
is not mutated.
