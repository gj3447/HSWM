# HSWM-DNRD-5 DGX live Q1 protocol

**Status:** v2 was refused before dispatch with zero POSTs. The separately
frozen v3 completed all 96 POSTs and reached
`LIVE_FALSIFIED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FROZEN_Q1`. Its single-use plan
is consumed and sealed. No Source A freeze, Permit, or DNRD-5 causal occurrence
has been created; the causal effect remains `NOT_EVALUATED`.

## Scope

Live Q1 is a finite-corpus observation: a 24-case, four-replica (96 POST) qualification of exact assistant-content UTF-8 repeatability for one pinned Qwen3.6/vLLM runtime pair on one exclusive loopback-ingress DGX lease. It reports only whether those four observed replicas were byte-identical for each frozen request under that observed configuration. It is not a performance comparison, correctness evaluation, causal experiment, provider-determinism proof, or scientific discovery.

The intended pair is `Qwen/Qwen3.6-35B-A3B-FP8` revision `95a723d08a9490559dae23d0cff1d9466213d989`, vLLM `0.25.1`, and the pinned local NVIDIA GB10 GPU with compute capability `12.1`. Those are empirical configuration identities, not a claim that the checkpoint is generally state of the art or superior. The model card documents native 262,144-token context and recommends vLLM 0.19 or newer. This short, non-thinking JSON qualification deliberately freezes 32,768 tokens to fit the single-GPU control surface; it does not qualify long-context, vision, thinking, tool-use, throughput, or benchmark capability. vLLM 0.25.1 calls batch invariance beta and does not list Qwen3.6/GDN among its tested models. The live v2 launch then directly falsified the stronger compatibility assumption: the pinned engine exited with `VLLM batch_invariant mode is not supported for GDN_ATTN.` The current stable documentation still does not list Qwen3.6 as batch-invariance tested. Therefore v3 deliberately does not enable or claim batch invariance; it tests only empirical exact-content repeatability across a frozen sequence of single-request calls. See the official [vLLM 0.25.1 batch-invariance contract](https://docs.vllm.ai/en/v0.25.1/features/batch_invariance/), the [recorded GDN/Qwen incompatibility](https://github.com/vllm-project/vllm/issues/48613), and the [current stable batch-invariance contract](https://docs.vllm.ai/en/stable/features/batch_invariance/).

The sole possible terminals are reproduced, falsified, inconclusive, or protocol/ledger/boundary void. A reproduced terminal is one necessary configuration qualification for considering a later, separately preregistered DNRD-5 causal test; it does not authorize that test, Source A, a Permit, Q2, a 300-block occurrence, outcome efficacy, HSWM learning, consciousness, selfhood, or scale-invariant causal closure.

## Corpus and identity boundary

The corpus is the checked Q0 public synthetic 24-case corpus, copied byte-for-byte then re-bound to the exact served-model identity and live request hashes. It contains eight cases in each declared class. It has no correctness evaluator, independent outcome, fresh holdout, or causal treatment; reuse therefore establishes only a stable response-repeatability input surface. In particular, any pass does not generalize to unseen prompts, prompt paraphrases, different seeds, sampling settings, scheduling or concurrency, hardware, drivers, vLLM versions, checkpoint revisions, context lengths, modalities, thinking or tool modes, providers, later times, or correctness and outcome behavior.

The six canonical identity blobs, exact model snapshot manifest, root genesis, 32-byte call-order seed, source/verifier commit-tree identities, and all request blobs are frozen before the first START. The v3 runtime fixes `--generation-config vllm`, eager execution, a one-sequence scheduler, disabled prefix caching, text-only loading, seed zero, and V1 multiprocessing disabled. Its runtime and declared-isolation identities bind `batch_invariant:false`, and the actual container is refused if any `VLLM_BATCH_INVARIANT` environment value is present. One sequence and a dedicated process reduce scheduling paths but do not become batch invariance by renaming. Model loading is offline. The container still uses a private Docker bridge whose host ingress is published only on `127.0.0.1`; outbound traffic is not attested absent, so the protocol makes no stronger network-isolation claim. Host IPC is not shared. The observed unit is one dedicated container process tree, not one operating-system PID.

After shared inference services and Ollama are quiesced, the preregistration freezes the exact sorted static non-Q1 host-listener endpoint set and a narrow dynamic-kernel-RPC policy. The DGX NFS client declares `nlm_tcpport=0` and `nlm_udpport=0`, so its kernel `lockd` ports are allocated dynamically and cannot honestly be frozen as static endpoints. Immediately before launch and at every live boundary, the launcher instead parses the local RPC registration table and requires exactly program 100021, service `nlockmgr`, owner `superuser`, versions 1/3/4 across `tcp`, `tcp6`, `udp`, and `udp6`. It derives exactly one IPv4 and one IPv6 wildcard TCP listener from those registrations and joins them to a non-interactive privileged `ss` observation. Each endpoint must occur in exactly one LISTEN row, both dynamic rows must report no userspace owner, and the registration and derived pair must remain unchanged for the whole lease. Every attestation carries the bounded, canonical sorted listener rows and their digest so the independent verifier can recompute endpoint multiplicity, the RPC-to-TCP join, and the complete inventory rather than accepting a self-asserted inventory digest. The complete observed listener set must equal the frozen static set plus that RPC-bound pair, and after launch plus the single Q1 loopback target. The launcher also rechecks the exact container/image/argv/cgroup, GPU process-tree membership, container network namespace and internal TCP listener, zero running requests, cumulative success count, and present zero-valued prefix-cache hit/query counters. A duplicate, new, missing, substituted, userspace-owned dynamic, unregistered, or mid-lease-drifting listener, foreign GPU process, absent metric series, or counter drift aborts the run. Static listeners are identified only by endpoint; the dynamic pair additionally has the bounded local `rpcbind` and privileged socket-row join. These are finite software observations, not a TEE, remote attestation, or proof of no interference. The options follow the official [vLLM engine-argument definitions](https://docs.vllm.ai/en/v0.25.1/configuration/engine_args/); the text-only setting is also the documented path for hybrid Qwen-family multimodal checkpoints. The [Qwen checkpoint card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8) supplies model metadata, not a repeatability guarantee. The content-addressed evidence root and its hash-chained ledger are research instruments, not HSWM cognition, world model, routing, or learning.

## Required chronology

1. Commit the runner, protocol, launcher, verifier, and freezer sources.
2. Save the selected GitHub API workflow-run JSON, the workflow-runs list JSON for the exact query `ci.yml`, `push`, `main`, exact head SHA, `per_page=100`, `page=1`, and the complete single-page jobs JSON. The offline projector requires that list to contain exactly one row equal to the selected run, joins the declared tree to `head_commit.tree_id`, and requires `CI`, `.github/workflows/ci.yml`, repository/head-repository identity, no pull requests, first attempt, ordered timestamps, and all-success jobs. The receipt embeds the exact raw inputs as canonical base64 with byte length and SHA-256, then independently rebuilds itself from those bytes. It remains an API projection rather than a cryptographic GitHub attestation.
3. Before freezing v3, run one separately identified zero-POST startup/readiness qualification with the exact proposed runtime controls. A target that cannot reach the bounded version/model/metrics surface is an operational refusal and must not create or consume a Q1 plan.
4. Create the six canonical identities, snapshot manifest, fresh root genesis, and seed; build the closed preregistration without a model call.
5. Commit the complete freeze under `_research/dgx_q1/preregistrations/`. External or merely ignored freezes are not executable. Obtain a later publication CI receipt for the exact clean publication checkout.
6. Supply that later publication CI receipt to the launcher. It proves the source/verifier commits are ancestors, refuses source drift between source and publication commits, and compares every local freeze file with the exact regular Git blob in the publication tree.
7. Atomically burn the plan hash at `/mnt/hswm/evidence/hswm-dnrd5-q1-live-consumption-v1`. The external marker binds the actual closure-manifest hash, evidence root, registry path, evidence mode, launch identity, and startup attestation. `PLAN_CONSUMPTION` must be the first hash-chained ledger row before any `PRE` or `START`. This is a node-local durable single-use guarantee, not distributed global consensus.
8. Only then can one exclusive lease execute the 96 zero-retry loopback calls. A breach seals the root; it is never resumed or moved to another registry.
9. Independently verify the sealed root and publish only its bounded qualification terminal. Injected fixture evidence is explicitly marked and can never yield a live reproduced/falsified terminal under the default verifier.

The publication receipt is distinct from the source/verifier receipts embedded in the plan. The evidence root belongs in a declared durable `hswm-run` output location. If launch or teardown fails, the uniquely named `--restart no` container is treated as suspect and removed before shared services are restored; a burned plan is never made reusable. Previously stopped `vllm`, `vllm-receiver`, `comfyui-10eros`, and Ollama are operational dependencies to restore after the bounded run, not experimental observations.

The initially published freeze at commit `48ee7fb9c7531e61ddb3272fad9ee715243b1cfd`, plan SHA-256 `f77d847346af9489229d2e4964f5f9c99b30d5738805abcbd06301e88428a7bd`, was superseded before launch because two host RPC listener ports changed after publication. It made zero model/provider calls, started no Q1 container, and created no plan-consumption marker. Inspection identified the changing sockets as the NFS kernel `lockd` IPv4/IPv6 TCP pair registered by `rpcbind`, not an inference service. A fully frozen endpoint baseline would therefore remain circular across NFS mount lifecycles; the replacement freezes static endpoints and the exact typed RPC classification while requiring the realized dynamic pair to stay fixed within the live lease. Any intervening source revision makes the old plan ineligible under the source-to-publication no-diff gate. This is a premarker operational refusal and protocol correction, not a Q1 result or scientific finding.

The replacement v2 freeze was published at commit `5a058dd284d1272e1d9d4038a53df615fd7ad415`, with plan SHA-256 `fd202af03af44aecea5b8271903e2e4151bee01ca7c27d915959fdb9939091b9`. Run `dgx-q1-v2-live-5a058dd-001` was refused during target startup on 2026-08-29. Its durable run receipt SHA-256 is `5cbb59d4b71024d0590be28608907286a4b1dece6523635f1064d1a733c308bc`; the archived artifact SHA-256 is `f97dcb63098323451cecf47773408ae39fa9b0a2c077ad663fdfbd051293d743`. The fail-closed output records zero durable START rows, zero completed response envelopes, exact provider/model-call upper bound zero, and no scientific claim. The durable plan marker is absent. A separate zero-POST exit diagnostic, receipt SHA-256 `3adc3d39155b036e91e61a0c8a4467c108e0aea2d6a8dfc03448d85793c0c8b6`, observed all 42 model shards load, Docker exit code 1, `OOMKilled:false`, and the exact GDN batch-invariance exception before container removal. Thus v2 is an unconsumed, superseded operational compatibility refusal—not reproduced, falsified, inconclusive evidence, a Qwen quality finding, or a DNRD-5 result.

Because v2 exposed no request to the model and no response was observed, v3 may reuse the same public-synthetic corpus and frozen call-order seed without response-conditioned selection. It must still have a fresh root genesis, changed runtime and isolation identities, new source/verifier and publication receipts, a new plan hash, and a separately checked-in freeze. The reuse improves direct comparability; it does not make the corpus a correctness evaluator or a holdout.

## Sealed v3 result

The v3 freeze was published at commit
`fddfe6eecdc508b1ad7fada114374fdc2dda265c`, tree
`6c6d3a2ad26a20e85e2db478d83d2f49c607a057`, after first-attempt CI run
[`33255350582`](https://github.com/gj3447/HSWM/actions/runs/33255350582)
completed all eight jobs successfully. The frozen plan SHA-256 is
`b054396e68620c2bcc97a9da9c429edda3182c93d41a573e6eef6fe30c997c22`;
its closure-manifest SHA-256 is
`04f16434ebea65f6a0551313c6686ab6dbe5668e8566cc7a5aa38bef71bae661`.

Run `dgx-q1-v3-live-fddfe6e-001` completed 96 START/response pairs with 96
successful HTTP responses and zero retries. The sealed ledger has 195 rows and
SHA-256
`f3cdfff46e1ee4ff0973531296863970f7bc9fa21eff1ea60ddc4da7a6e13f00`.
The frozen independent verifier reproduced the terminal
`LIVE_FALSIFIED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FROZEN_Q1`: 23 of 24 cases had
four identical assistant-content byte strings, while `QCASE-024` had three
copies with SHA-256
`14bc62d62791f445e539a4c4e1f212c0d7e5d818095ae87608fcc8eabf262a31`
and one semantically different rationale with SHA-256
`b8dba1c6c5d591e9460923c93bc3b129686ff97e1fef1d33a99f261df02d6d23`.
The four answer fields all contained `VISTA`, but that field-level observation
is post-hoc descriptive evidence, not the primary endpoint or a correctness
result.

The external consumption marker has SHA-256
`7196b27a29b61087413c756a0823105258063ff06903f48c0e6f8518c9ed655a`.
This plan and root must never be repaired, resumed, replaced, relabeled, or
rerun. Under the exactness-policy amendment, the resulting Source-A disposition
is `SOURCE_A_REFUSED_EXACTNESS_UNQUALIFIED`. It authorizes no Source-A freeze,
Source B, future randomness, causal occurrence, or effect claim. DNRD-5 causal
calls remain zero and its causal effect is `NOT_EVALUATED`, not a zero or null
effect.

The exact result, ledger, execution and independent-verification receipts, and
the two distinct `QCASE-024` content byte strings are published in
[`results/HSWM_DNRD5_DGX_LIVE_Q1_RESULTS_2026-08-29.md`](../../results/HSWM_DNRD5_DGX_LIVE_Q1_RESULTS_2026-08-29.md).
No live-KG update follows because the result neither tests nor changes any FCL
law, HSWM-of-HSWMs composition claim, or constitutional identity claim.

## Result-template interpretation

Any published terminal must name the exact frozen corpus, four-replica observation, model/runtime identity, and lease as its scope. A reproduced terminal means only that all four observed assistant-content UTF-8 values matched for every frozen request in that serialized run; a falsified terminal means that at least one recorded comparison did not match. Neither terminal qualifies batch invariance, estimates a population repeatability rate, establishes deterministic behavior beyond the finite serialized configuration, validates answer correctness, measures an outcome, identifies a causal effect, or tests any FCL law. `INCONCLUSIVE` and `VOID` are non-results, not evidence for or against DNRD-5. No Q1 result changes the constitutional target or the scientific status `SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`.

## HSWM and FCL boundary

HSWM remains the constitutional target: one token-native LLM-function macro-neural network whose evolving hypergraph jointly realizes living harness, world model, and continuous learner. This Q1 instrument neither realizes nor demonstrates that target. The repository, CI, launcher, DGX, KG, and receipts are bounded projections/interfaces.

All eight FCL laws remain unchanged, including same-rule recursive HSWM-of-HSWMs composition. The scientific position remains `SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`: theory supplies typed bridges and falsifiable future tests, not proof of cognition, selfhood, consciousness, or scale-invariant causal closure. Do not update the live KG or `F1_R8_RESULTS_LOG.md` unless a material, checked and independently verified research result exists.
