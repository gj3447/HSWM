# HSWM-DNRD-5 QCASE-024 mechanism-isolation diagnostic

- Date: `2026-08-29`
- Instrument: `DNRD5-QCASE024-MI-1-CONTENT-V4`
- Status: `IMPLEMENTED / PRE-FREEZE / UNRUN`
- Namespace: `DNRD5-QCASE024-MECHANISM-ISOLATION-ONLY/v4`
- Scope: post-result-selected finite mechanism diagnostic
- DNRD-5 causal effect: `NOT_EVALUATED`
- Source-A disposition remains: `SOURCE_A_REFUSED_EXACTNESS_UNQUALIFIED`
- v4 is a fresh content/trace-qualification experiment identity.  Its source
  and publication identities, CI receipts, freeze, plan hash, marker, closure,
  genesis, consumption registry, and live-run identifiers do not exist yet and
  must be bound before any target launch.

## Historical v3 one-call content-normalization incompatibility

v3 qualified the closed `usage` rule after the v2 failure.  Its source/verifier
commit was `a29230adadb273b98837981424bdb4b1b2a218d7`, with tree
`94721df4543000da8a740dabdab26b7af808f988`.  First-attempt source CI run
`33265653993` completed `8/8 SUCCESS`; its receipt SHA-256 is
`766494ce20254a9ec0d02fb72fb3eacc6d02b74b85c2dee04a1be9227910c7ce`.
The separately qualified publication commit was
`97fd9032680f78324fce1a437b73fca833879b0d`, with tree
`c304cb9b8065e7d4bc29138fcee7fad8beff1c77`.  Publication CI run
`33266180588` completed `8/8 SUCCESS`; its receipt SHA-256 is
`3756f1b72d319c2a2395ab9811e97c1069846dd766b5e7e75a47da7060a6261f`.

The immutable v3 freeze is
`_research/dgx_mi/preregistrations/hswm-dnrd5-qcase024-mi-1-usage-v3-2026-08-29`.
It bound plan SHA-256
`3aeaebbaed690c6b7cc53bafdea32979c42a74f45990030ab07fcea3452af4ea`,
start-marker SHA-256
`890748b6e4a526de075c6a53a2ae0cf025ed738b38670f926364a317bc5fb8ea`,
closure-manifest SHA-256
`33c8d500c496112f5f9b9968a57876aaaf30738e27a065a9c715b24d38989cf9`, and
root-genesis SHA-256
`17926235302366fb367aac22ec6060e695939124316345578d92ce3c20561fb1`.

That one-time plan was consumed once in its declared registry
`/mnt/hswm/evidence/hswm-dnrd5-qcase024-mi-1-usage-v3-consumption-v3` and
launched as `dgx-qcase024-mi-1-v3-live-97fd903-001`.  The external consumption
marker SHA-256 is
`85e15079c3e9974d3b9958701076d1cee909ce2ee685b004765f7a97947e2ea4`.
The wrapper receipt SHA-256 is
`c42f1e340fbc3ea4d0d5e771f18f93e21d18bb772f5f94b0ddeb587bb802c5ee`; its
archived artifact SHA-256 is
`6bb23380fdfc611d10afcdb9a9da5bb921a3191e8e4931a23d31487acaa5c5c1`.
The six-record ledger SHA-256 is
`947620c9dd1fb0e4b4d6cd3922ecf0e3f9797aa08cac75bf1661e2aa3e03fd12`, and
the final-record SHA-256 is
`55707fd38d8e977c498813642f6901fb9a1fc4e9ea8a6a4040f6a4f058495284`.
It sealed as `INCONCLUSIVE_DGX_QCASE024_MI_INCOMPLETE_LIVE_SLOTS`: one START,
one preserved raw envelope, zero accepted slots, zero completed blocks, and no
observation-pattern label or arm inference.

The sole started slot was `MI-024-V3-ASYNC_ENABLED-B01-R001`.  Its HTTP status
was `200`; the 94,727-byte raw envelope SHA-256 is
`b148d859f093f2bc032847779e0a79608849b595874cb2dea1ac6e7f479e4d5f`.
The v3 usage rule passed: `prompt_tokens=168`, `completion_tokens=59`,
`total_tokens=227`, and `prompt_tokens_details=null`.  The assistant content
was valid ordinary pretty UTF-8 JSON (234 bytes), with answer `VISTA` and the
same Q1 modal rationale.  The runner nevertheless applied canonical-JSON
parsing directly to that ordinary provider content and raised
`CANONICALJSONERROR`.  This is an instrumentation content-normalization
failure, not a model-content failure and not a scientific observation.

The preserved logprob trace has 59 rows of 20 candidates.  The first 58 row
byte arrays concatenate exactly to the 234 content bytes.  The final, excluded
row is the exact Qwen terminal token `<|im_end|>` with UTF-8 bytes
`b"<|im_end|>"`, log probability `0.0`, and SHA-256
`d6b60b51acc9448b15da9cb03f644d0ec8c410e37735817f39e15764aa75a37f`.
The provider correctly omitted that terminal token from `message.content`; v3
incorrectly treated all returned token rows as content-aligned.  Independent
verification ran once as `dgx-qcase024-mi-1-v3-verify-97fd903-001`; its output
SHA-256 is
`6d24263135a6701753f8b0d3b7eb07e4f66e7d9418185e703a0f8acbede086ca`, its
receipt SHA-256 is
`8dc02a306e7231936b4ecbd85fc1802c1a2988224ba70e248ea04cbcecef808d`, and its
archived verifier artifact SHA-256 is
`da77923ed5a21ce1e8474abafb82b1d39a8276876b4b861d1191740ff651f97e`.

The exact archived raw envelope was also streamed through the candidate v4
producer parser before freeze.  The bounded qualification record is
`_research/dgx_mi/qualifications/hswm-dnrd5-qcase024-mi-1-content-v4-v3-envelope-replay-2026-08-29.json`.
It records the 234-byte exact provider content, 225-byte structured diagnostic,
and 97,220-byte exact-decimal trace projection: all 59 rows had a selected
candidate in 20 unique `(token, bytes)` candidates, while the 58 nonterminal
rows alone reconstructed the assistant content.  This qualifies one preserved
historical envelope against the candidate v4 parser.  It is not a live v4
observation, an observation-pattern label, or a scientific result.

v3 is permanently sealed and must never be retried, resumed, replaced,
transferred, or reused.  v4 is not a continuation or repair of the v3 plan: it
is a fresh identity that preserves the science design and changes only the
content normalization and token-boundary qualification described below.

## Historical v2 one-call envelope incompatibility

The v2 closure-qualified source commit was
`1f7541357876d1d73f9faeb6ab96247dbecde048` with tree
`fc948b0e872a01a0ab7ca6b5cf1cac0832b03f9b`. Its first-attempt source CI run
`33262943949` completed `8/8 SUCCESS`; the source-CI receipt SHA-256 is
`11eb542d57ad5240a4ee7b521ddf45a07393617bf90b920dc16f1f1f0186b8ca`.
The separate v2 freeze at
`_research/dgx_mi/preregistrations/hswm-dnrd5-qcase024-mi-1-closure-v2-2026-08-29`
bound plan SHA-256
`481b203b3393440f63a53fefec44f4bca4d1fa1c06f00c1c9cbb3a6d704c6432`,
start-marker SHA-256
`baf4ab53410e24b82d61f208dceca62593dd0543f4c7b80f1d2cc49bc286a8b0`,
closure-manifest SHA-256
`63e70d81a398bee04148e27170af35f410dc4cef3dd2060c29b69b27b7126b83`, and
root-genesis SHA-256
`cf4ab30558c41e05d68c7f076d99d60e05da68e26f647bfc0913ab84fad6b58a`.

The qualified publication commit was
`d97f6702bcbb055c22cdd8e2a68bc296e3a50fb8` with tree
`18f848c3f40df57bdc5d40c2a334ca8dcfe5b68d`. Its publication CI run
`33263553497` completed `8/8 SUCCESS`; the publication-CI receipt SHA-256 is
`51a761684a836c9e8e1037d3cca2d19935896c3740646b8c59cd3bf7b864bb91`.

That one-time v2 plan was durably consumed in its own declared registry and
launched once as `dgx-qcase024-mi-1-v2-live-d97f670-001`. The wrapper receipt
SHA-256 is
`bc53a5e508521c481eee8a5396f338395c66bc31f1c0d5ede082c7aae49bee2a`.
The ledger contains one plan-consumption record, one MI marker, one block start,
one `START`, one failed slot terminal, and one run seal. Its SHA-256 is
`6593626c0ab48753799b173d94ea3cd5e1825755e74716a8f75e846fc4d450d3`; the
final-record SHA-256 is
`5bd092710f12129648f0ed615dfbdff19f9dcfa68e6d19fc5f66e7aeb1a744a9`.
The root sealed as
`INCONCLUSIVE_DGX_QCASE024_MI_INCOMPLETE_LIVE_SLOTS`, with one started slot,
zero successful slots, and no retry, replacement, resume, or transfer.

The sole slot was `MI-024-V2-ASYNC_ENABLED-B01-R001`. Its transport status was
`200`; its preserved raw OpenAI-compatible envelope is 78,220 bytes with
SHA-256
`4d2f2e95ce0e7e59fbac3b45f26a278035b145b025b231bd124e14b3c5a1daa8`.
The envelope supplied the ordinary three integer usage counts and the additional
literal-null field `prompt_tokens_details`. v2 had incorrectly required the
usage object to have exactly the three count keys, so the runner refused the
response before accepting an observation. The raw envelope is retained; this
was an evidence-envelope compatibility failure, not a model-content failure or
an observed mechanism pattern. The response has zero accepted slots, zero
completed blocks, zero arm reduction, and no one of the four preregistered
observation-pattern labels.

Independent verification ran once as
`dgx-qcase024-mi-1-v2-verify-d97f670-001`. Its output SHA-256 is
`f0a21b785e4afad1824aa49d3df1d08b46c8bffcde822c5c9f42e2980112bebd`, and its
wrapper receipt SHA-256 is
`055d2364214b2a70d61b5a16f9469479cbc8e15dd4a6bfc7914f87218e799bae`. It
independently reported the same v2 plan, ledger, final record, and
`INCONCLUSIVE_DGX_QCASE024_MI_INCOMPLETE_LIVE_SLOTS` terminal.

v3 was a fresh experiment identity, not a continuation, retry, or repair of v2.
It preserved the question, Q1-selected material, pinned model/runtime, ABBA
order, four fresh-server blocks, 16-call budget, zero-retry rule, and causal
nonclaims.  Its closed `usage` acceptance rule required the three count fields
to be non-Boolean, non-negative JSON integers satisfying
`prompt_tokens + completion_tokens = total_tokens`; the sole optional field was
`prompt_tokens_details`, accepted only when literally `null`.  Unknown fields,
a missing count, a non-null optional value, non-integer number, Boolean,
negative value, or failed sum invariant refused the slot.  That corrected
usage rule passed in the sealed v3 call; it is retained unchanged by v4.

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

The fresh v4 qualification retains the corrected v3 usage boundary and adds
only the content and token-boundary rules identified by the sealed v3 run.  It
does not change the research question, material, request, model/runtime pins,
ABBA order, 16-call budget, zero-retry rule, reductions, or nonclaims.  The v2
and v3 freezes, consumption records, raw envelopes, ledgers, verification
outputs, and historical results remain immutable evidence; no historical
identifier or plan may be reused.

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
documents the Grace Blackwell GB10 platform and 128 GB unified memory.  The
version-matched [vLLM engine-argument reference](https://docs.vllm.ai/en/v0.25.1/configuration/engine_args/)
also documents the frozen 20-logprob cap and `processed_logprobs` mode.

Those are current, capable research components, not proof that this checkpoint
is universally state of the art. This diagnostic uses only a short text-only,
non-thinking request at a frozen 32,768-token server limit. It does not test
vision, long context, coding benchmarks, tool use, throughput, fine-tuning, or
model superiority.  NVIDIA's 2026-08-25
[DGX Spark release notes](https://docs.nvidia.com/dgx/dgx-spark/release-notes.html)
list driver `580.159.03`, newer than the observed and frozen `580.126.09` on
this node.  The study does not upgrade it: changing the driver would add a
second intervention and destroy the intended Q1-to-MI runtime comparison.
Thus “advanced-model boundary” means a revision- and hardware-pinned capable
stack, not the latest available version of every component.

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

## Fresh v4 content and trace qualification

Before v4 may freeze, its producer and independent verifier must implement and
offline-qualify the same two fail-closed contracts against the preserved v3 raw
envelope.  This is a measurement-boundary correction only; it does not turn the
v3 response into an accepted observation or alter the fixed scientific design.

`CONTENT_NORMALIZATION/v4` requires strict, finite UTF-8 JSON with duplicate
object keys refused.  The exact provider `message.content` UTF-8 bytes are
retained as received.  After ordinary JSON parsing and response-schema
validation, a separate canonical structured diagnostic may be derived; the
provider content itself must not be required to be canonical JSON.

`TOKEN_ALIGNMENT/v4` requires every returned processed-logprob row to retain
its provider byte array and exactly 20 top-logprob candidates whose
`(token, bytes)` identities are unique within that row.  The concatenated
bytes of all nonterminal rows must equal the exact assistant-content UTF-8
bytes.  Exactly one final, excluded terminal row is required; its token and
bytes must be `<|im_end|>` and `b"<|im_end|>"`, respectively, with the pinned
terminal-byte SHA-256
`d6b60b51acc9448b15da9cb03f644d0ec8c410e37735817f39e15764aa75a37f`.
That terminal row remains in the raw envelope and deterministic full-trace
projection but is
excluded from byte-content comparisons and divergence reductions.  Missing,
extra, misplaced, malformed, or nonmatching terminal rows, nonmatching content
bytes, a malformed row/candidate, or a candidate count other than 20 refuse the
slot.  Its derived full-trace projection is canonical JSON whose log
probabilities are exact normalized decimal strings; the raw envelope remains
the byte-exact source for original numeric lexemes.

The implementation was offline-qualified against the exact 94,727-byte v3 raw
envelope, read from the archived artifact whose SHA-256 is
`6bb23380fdfc611d10afcdb9a9da5bb921a3191e8e4931a23d31487acaa5c5c1`.
The v4 parser accepted the 234 exact content bytes, derived structured-content
SHA-256
`58b4830cb693325699dfbbd123ef8c266a005f6627b8eab15c8c75865d6a78eb`,
split 59 full trace rows into 58 semantic rows plus one terminal row, and
reproduced terminal-byte SHA-256
`d6b60b51acc9448b15da9cb03f644d0ec8c410e37735817f39e15764aa75a37f`.
The resulting exact-decimal canonical trace-projection SHA-256 is
`ef4a90844d96afb471f5bc5865efc5063bb9f2ad2d23eb6ed141ca01e2e1cb9a`.
This qualification repairs the instrument boundary only; it is not a v3
observation, an arm comparison, or a scientific result.

The fresh v4 namespace, source/build and independent-verifier identities,
source and publication qualification, freeze, plan burn, cache namespace,
evidence root, consumption registry, and verifier run must all be new.  The
offline v3-envelope qualification is complete; no v4 target call is authorized
until the remaining source/publication and freeze bindings are complete.

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
   deterministic full token-trace projection hashes.

Token alignment uses the response's explicit byte arrays under
`TOKEN_ALIGNMENT/v4`: nonterminal emitted-token bytes must reproduce
assistant-content UTF-8 exactly, while the single pinned final terminal row is
retained but excluded. Numeric log probabilities are parsed losslessly and
published as normalized decimal strings, not binary floating-point values. If
the peer token or best competitor is not available in the returned top 20, the
reducer records an explicit unavailable state and never invents a gap. No
arbitrary “near-tie” threshold is declared; the exact observed gaps are
descriptive diagnostics.

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
identity separation, response/content/schema join, `CONTENT_NORMALIZATION/v4`,
`TOKEN_ALIGNMENT/v4`, and all descriptive reductions. Raw OpenAI-compatible
envelopes contain decimal numbers and are preserved as ordinary strict JSON;
they are not falsely labeled canonical-json/v1.

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
