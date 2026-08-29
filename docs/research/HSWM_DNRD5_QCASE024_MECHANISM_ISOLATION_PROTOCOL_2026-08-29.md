# HSWM-DNRD-5 QCASE-024 mechanism-isolation diagnostic

- Date: `2026-08-29`
- Instrument: `DNRD5-QCASE024-MI-1-CLOSURE-V2`
- Status: `CLOSURE_LOADER_QUALIFICATION_V2_IMPLEMENTED / UNRUN /
  AWAITING_SOURCE_CI_AND_FRESH_PREREGISTRATION`
- Namespace: `DNRD5-QCASE024-MECHANISM-ISOLATION-ONLY/v2`
- Scope: post-result-selected finite mechanism diagnostic
- DNRD-5 causal effect: `NOT_EVALUATED`
- Source-A disposition remains: `SOURCE_A_REFUSED_EXACTNESS_UNQUALIFIED`

## Historical v1 pre-launch refusal

The first checked-in freeze remains immutable at
`_research/dgx_mi/preregistrations/hswm-dnrd5-qcase024-mi-1-2026-08-29`.
Its plan, start marker, closure, and genesis SHA-256 values are respectively
`eae4f428a02d16d89500bbbbc26157f82dc7a956f4b319ea5df1b4a8902b82b9`,
`4c158f819ab91f1e6382c61e4545af131f74dddcda5f6a310d51136057e5a6d8`,
`4b79f7020db05f9682a5506d3477878a8af219a491db997b58839870fe76355d`,
and `19c1229a1e9bf33115ccea4875ab77cb88d31b1cc335414044177524e3b6c530`.

Publication commit `9ae0e9ade26d663535bdeaf1b9af478396734132` was invoked once as
DGX wrapper run `dgx-qcase024-mi-1-live-9ae0e9a-001`. It exited with
`MI_REFUSED:KeyError` before `MiRunner` construction because the validated
closure loader returned only the closure-declared artifacts while the
production handoff then requested `closure_manifest.json` from that mapping.
The wrapper receipt SHA-256 is
`6e22a16ae07f20bf52bbd11a370d995277205ad0c1faff18fe3bf01de38cfe7c`.
The run artifact contains no MI evidence root, ledger, START record, raw
response, or plan-consumption marker; the declared v1 registry is empty.
Therefore the exact target/model-call count and plan-burn count are both zero.
This is a pre-launch software integration defect, not a scientific observation
or one of the frozen MI observation patterns.

The active v2 qualification changes only this handoff: after validating every
declared artifact and the complete filesystem closure, the loader returns the
already validated closure bytes separately to the runner assembly. It also uses
v2 typed identifiers, attempt IDs, fresh genesis, cache namespace, and a distinct
node-local consumption registry so the v1 freeze cannot be launched as v2. The
question, material, request, model/runtime pins, ABBA order, 16-call budget,
zero-retry rule, terminal taxonomy, reductions, and nonclaims are unchanged.

## Question and conceptual delta

DGX live Q1 v3 completed 96/96 calls but falsified its exact assistant-content
repeatability endpoint because one of four `QCASE-024` rationales differed. That
sealed result is not reopened, retried, repaired, or replaced. The present
instrument asks a narrower follow-up question: under the same pinned model,
hardware, request meaning, and single-sequence serving controls, is further
`QCASE-024` output variation observed when vLLM's asynchronous scheduling is
explicitly enabled versus explicitly disabled?

`QCASE-024` was selected after reading Q1 v3 because it was the only varying
case. This selection makes the diagnostic explicitly post-result and
non-confirmatory. Its observations cannot estimate a corpus or provider-wide
repeatability rate, rescue Q1, qualify Source A, or identify a causal mechanism.
The conceptual delta is mechanism localization, not a new HSWM architecture or
a larger harness.

## Source result and fixed material

The selection is bound to Q1 result commit
`a6f13445375f8195a35e025810cc1628c41b5641`, result evidence SHA-256
`cc53ba6d42ebe52d648fbd777850b9b96c9ae50e7fda99aa5cf7456a6344b51f`,
Q1 plan SHA-256
`b054396e68620c2bcc97a9da9c429edda3182c93d41a573e6eef6fe30c997c22`,
and ledger SHA-256
`f3cdfff46e1ee4ff0973531296863970f7bc9fa21eff1ea60ddc4da7a6e13f00`.
The prior request SHA-256 was
`c24c74241bbf670b3e2c640f3acd18cb449d3172659bde5fcb08262950a53a19`.

The following checked-in Q1 v3 material bytes remain fixed:

| Material | Bytes | SHA-256 |
|---|---:|---|
| Instruction | 128 | `8e13131449ba0f31cb7305490dec680f6808006db2e5b50cc8614b172c85b907` |
| Model input | 225 | `5902dec004e606aaf46b8a5d80c45ab855f275d714d111b2430d86d0e1c1a273` |
| Response schema | 285 | `a623afd2cace659731c46b336fd4cb75c071e60f425fa583e8995abe7ff83940` |
| RNG bytes | 32 | `69b1f0ef2be0d6519baa19562928cc6ed3a458e382e48508a4cb47292063bd78` |

The diagnostic request changes only the common measurement surface required in
both arms: `logprobs=true` and `top_logprobs=20`. Thus its request hash must
differ from Q1's prior no-logprobs request. The request otherwise fixes the
served model, system/user messages, strict response schema, Q1-derived seed,
`temperature=0`, `top_p=1`, `n=1`, `stream=false`, thinking disabled, and
`max_tokens=256`. The resulting instrumented request SHA-256 is
`fec3b64ce00d750e67a34374fe9d1e5e7fa6232294b8990e0aa4f352bc52fac9`.

Returning log probabilities is itself an intervention on the serving path: it
adds work and observability that Q1 did not request. The arm contrast remains
matched because both arms receive the same instrumented request, but neither
arm can be treated as a byte-for-byte replay of Q1. A result from this study can
localize variation within this instrumented configuration; it cannot by itself
identify the cause of the already sealed Q1 variation.

## Pinned advanced-model boundary

The runtime remains `Qwen/Qwen3.6-35B-A3B-FP8` revision
`95a723d08a9490559dae23d0cff1d9466213d989`, snapshot-manifest SHA-256
`2ece6b46248e818cbf93aa30299300f7dd4c60d9351960ec790cc8b420376e47`,
vLLM `0.25.1`, and the pinned NVIDIA GB10 GPU. The Qwen
[model card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8/blob/95a723d08a9490559dae23d0cff1d9466213d989/README.md)
describes a 35B-total/3B-active hybrid Gated DeltaNet/full-attention MoE with
FP8 weights and a native 262,144-token context. NVIDIA's
[DGX Spark hardware guide](https://docs.nvidia.com/dgx/dgx-spark/hardware.html)
documents the Grace Blackwell GB10 platform and 128 GB unified memory.

Those are current, capable research components, not proof that this checkpoint
is universally state of the art. This diagnostic uses only a short text-only,
non-thinking request at a frozen 32,768-token server limit. It does not test
vision, long context, coding benchmarks, tool use, throughput, fine-tuning, or
model superiority.

## Frozen 2×2 blocked design

The sole planned budget is 16 live POSTs in four fresh-server blocks. Block
order is fixed as ABBA to balance coarse monotonic time/order exposure:

| Position | Arm | Block | Calls |
|---:|---|---|---:|
| 1 | `ASYNC_ENABLED` | `B01` | 4 serial |
| 2 | `ASYNC_DISABLED` | `B01` | 4 serial |
| 3 | `ASYNC_DISABLED` | `B02` | 4 serial |
| 4 | `ASYNC_ENABLED` | `B02` | 4 serial |

No requests are concurrent. Each block launches one new container/process,
executes replicas `R01` through `R04` in that exact order, tears the container
down, and verifies target GPU/listener quiescence before the next block. Each
block gets distinct initially empty Hugging Face and compile-cache directories;
the read-only model snapshot and physical GPU are deliberately shared. “Fresh
server” therefore means fresh container, vLLM process, KV/session state, and
declared cache directories, not fresh hardware or new model weights.

Both arms freeze the Q1 v3 controls: image digest and ID, revision-bound model
snapshot, dedicated GPU/process, bridge network with loopback-only host ingress,
private IPC, offline model loading, `max_num_seqs=1`, prefix cache off,
`--enforce-eager`, engine seed zero, language-model-only loading,
`VLLM_ENABLE_V1_MULTIPROCESSING=0`, and
`CUBLAS_WORKSPACE_CONFIG=:4096:8`. Both also add server
`--max-logprobs 20 --logprobs-mode processed_logprobs`. The sole arm-level
engine-argument contrast is the documented Boolean pair: `ASYNC_ENABLED`
includes `--async-scheduling`, while `ASYNC_DISABLED` includes
`--no-async-scheduling`. Explicitly pinning both sides avoids relying on a
runtime default.

vLLM states that it does not guarantee reproducibility by default and that
online scheduling-independent reproducibility requires batch invariance; see
the official [reproducibility contract](https://docs.vllm.ai/en/stable/usage/reproducibility/).
The pinned Qwen3.6 GDN path rejected batch invariance before dispatch in Q1 v2,
so this experiment does not retry or claim that unsupported control.
`--no-async-scheduling` is an available
[vLLM engine argument](https://docs.vllm.ai/en/v0.25.1/configuration/engine_args/),
not a documented end-to-end determinism guarantee.

A separate open vLLM engineering
[issue](https://github.com/vllm-project/vllm/issues/51562) reports that a shared
GatedDeltaNet metadata path can misclassify a stateless one-token first chunk
and potentially read a recycled state page. The report explicitly says its
state-inheritance consequence was inferred from the code path rather than
shown in end-to-end generation. Its stated trigger also does not establish
that Q1's longer QCASE-024 prompt took that path, and the issue does not list
this exact pinned checkpoint/runtime pair. It is therefore retained only as an
alternative implementation hypothesis, not as a discovered cause or a factor
in MI-1.

## Primary observations

The diagnostic has no efficacy endpoint and no causal “winner.” The frozen
reducer reports:

1. exact assistant-content UTF-8 cardinality for every four-call block, each
   eight-call arm, and all 16 calls;
2. each block and arm's modal-byte count;
3. for every unequal predeclared comparison, the first differing content byte,
   the corresponding completion-token spans, the emitted tokens, their
   reported processed log probabilities, and available competing-token gaps;
4. exact raw-envelope, assistant-content, canonical structured-content, and
   canonical token-trace hashes.

Token alignment uses the response's explicit byte arrays. Concatenating emitted
token bytes must reproduce assistant-content UTF-8 exactly. Numeric log
probabilities are parsed losslessly and published as normalized decimal strings,
not binary floating-point values. If the peer token or best competitor is not
available in the returned top 20, the reducer records an explicit unavailable
state and never invents a gap. No arbitrary “near-tie” threshold is declared;
the exact observed gaps are descriptive diagnostics.

The complete observation pattern is one of:

- `ALL_ARM_BLOCKS_EXACT`
- `ASYNC_ENABLED_VARIATION_ASYNC_DISABLED_EXACT`
- `ASYNC_DISABLED_VARIATION_ASYNC_ENABLED_EXACT`
- `BOTH_ARMS_VARIATION`

These labels describe finite bytes. They do not name a cause.

## Fail-closed execution and terminals

A new plan, root genesis, freeze closure, source/build identities, independent
verifier source, and node-local consumption registry are required. One atomic
plan burn occurs before the first target launch. All 16 request blobs and four
block configurations are durable before dispatch. Every START is fsynced before
its single POST; every slot has zero retry, replacement, resume, or movement to
another block. A content difference does not stop the fixed budget early.

Identity, listener, GPU, argv, cache-freshness, request, transport, response,
logprob, ledger, or teardown breach seals the whole root. It does not authorize
later blocks. The top-level terminals are:

- `LIVE_COMPLETE_DGX_QCASE024_MECHANISM_DIAGNOSTIC`
- `INCONCLUSIVE_DGX_QCASE024_MI_INCOMPLETE_LIVE_SLOTS`
- `INCONCLUSIVE_DGX_QCASE024_MI_REQUIRED_LOGPROB_OR_ALIGNMENT_UNAVAILABLE`
- `VOID_DGX_QCASE024_MI_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH`

The independent verifier rederives the freeze, plan burn, exact request, 16-slot
order, hash chain, per-block server identity continuity, cross-block server
identity separation, response/content/schema join, byte-token alignment, and
all descriptive reductions. Raw OpenAI-compatible envelopes contain decimal
numbers and are preserved as ordinary strict JSON; they are not falsely labeled
canonical-json/v1.

No user echo or hash-ratification message is required. The checked-in freeze,
clean source/publication commits, first-attempt successful CI receipts,
single-use external marker, and frozen verifier form the executable chronology.

## Interpretation boundaries

- Variation in async-enabled with eight exact disabled-arm responses is consistent
  with a scheduler-sensitive serving path, but server start, time, kernel, GDN,
  and FP8 paths remain possible confounders. It is not proof of scheduler cause.
- Variation with async disabled shows that disabling async scheduling is not a
  sufficient remedy in this finite configuration. It does not prove that the
  scheduler contributes nothing.
- Exact bytes in both arms are inconclusive about the already observed Q1
  variation and never reverse Q1's sealed falsification.
- A small returned competing-token gap is consistent with near-tie
  amplification. It does not identify GDN, FP8, a kernel, or a reduction path
  as the cause.

Separating GDN from FP8 or lower-level reduction behavior requires a later,
distinct checkpoint, precision, or backend factor experiment. Changing those
factors would no longer be the same Q1 configuration.

## HSWM and FCL boundary

HSWM remains one token-native LLM-function macro-neural network whose evolving
hypergraph jointly plays living-harness, world-model, and continuous-learner
roles. This diagnostic is a bounded evidence instrument, not HSWM cognition,
routing, world modeling, or learning. It neither tests nor changes the eight FCL
laws or same-rule recursive HSWM-of-HSWMs composition.

The scientific status therefore remains
`SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`. No result from this
diagnostic can establish consciousness, selfhood, scale-invariant causal
closure, outcome-bound causal learning, or HSWM efficacy. DNRD-5 causal calls
remain zero unless a future, separately qualified Source-A chronology is ever
created; this diagnostic itself cannot create one.
