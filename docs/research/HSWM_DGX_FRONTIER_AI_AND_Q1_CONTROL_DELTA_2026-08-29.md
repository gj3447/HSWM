# HSWM DGX frontier-AI and Q1 control delta

- Date: 2026-08-29
- Scope: DGX provider-control finding and research-neighbour update
- Decision: `Q1_REFUSED_IN_OBSERVED_CONFIGURATION / NO_DNRD5_OCCURRENCE`
- Scientific status: `SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`
- Performance-claim boundary: `NO_SOTA_RANKING / NO_COMPARATIVE_BENCHMARK`

## Canonical role and evidence boundary

HSWM's target identity remains one token-native LLM-function macro-neural
network whose evolving canonical hypergraph jointly serves as living harness,
world model, and continuous learner.  Its canonical learning claim requires an
outcome-bound, permitted, owner-valid revision to cause changed subsequent
behaviour on a fresh probe.  A DGX host, model server, cache, prompt, knowledge
graph, repository, evaluator, receipt, or test is a bounded interface or
measurement, not HSWM cognition, learning, or a substitute for that loop.

All eight fractal composition laws (FCL-1 through FCL-8) remain target
constraints.  In particular, HSWM-of-HSWMs means same-rule recursive
composition of cognition-bearing HSWMs under typed, outcome-bound dynamics;
neither multiple processes on one GPU nor a nested software graph demonstrates
that invariant.  This document adds neither a scientific discovery nor evidence
of consciousness, selfhood, causal closure, HSWM efficacy, or a causal effect.

## Observed DGX serving configuration

The following read-only observation was made on 2026-08-29. It is not a
Source-A freeze, an attestation of exclusive control, or a general claim about
DGX Spark deployments. No model request was sent. DMI identifies this host as
an MSI `MS-C931` EdgeXpert rather than an NVIDIA Founders Edition unit, so an
NVIDIA Founders Edition release table must not be used by itself to declare the
OEM stack current or stale.

| Field | Observed value | Q1 implication |
| --- | --- | --- |
| Host | MSI EdgeXpert `MS-C931`; Ubuntu 24.04.4 LTS; AArch64; bounded platform projection SHA-256 `0f46ded2b663d057437e218361c805452995ea3a4e89abf0359485e6c92248a2` | Product identity and OS identify the observation, not a benchmark or isolation boundary. |
| GPU and driver | NVIDIA GB10, UUID `GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5`; driver `580.126.09`; MIG query `[N/A]` | One shared accelerator is not a dedicated-GPU receipt; `[N/A]` is retained as an observation rather than interpreted as a general capability proof. |
| Target model/runtime | `Qwen/Qwen3.6-35B-A3B-FP8`; served as `qwen3.6-35b-a3b`; vLLM `0.25.1` | This is a capable serving candidate, not exact response determinism or a performance ranking. |
| Runtime image | configured as `vllm/vllm-openai:latest`; image ID `sha256:30a38a1d74a17365eca400e83ffd885b250e0c8c0d3c5b508afa8c412d2ddf95`; repository digest `vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089` | The observed bytes have identities, but startup through a mutable tag is not a digest-pinned fresh launch. |
| Model revision | cache ref `95a723d08a9490559dae23d0cff1d9466213d989`; no `--revision` in the serving command | A cache ref cannot retroactively establish which revision startup resolved or bind exact model/tokenizer files. |
| Context and scheduler | `max_model_len=32768`; `max_num_seqs=6` | Concurrent scheduling violates Q1's one-sequence boundary; 32K is a deployment choice, not the model's maximum. |
| Batch invariance | `VLLM_BATCH_INVARIANT=1` not observed | Default online serving does not supply the declared batch-invariance control. Enabling the beta flag would still require model/version qualification. |
| Prefix cache | explicitly enabled; counters `351609` queries and `29568` hits at observation | This is a candidate cross-request caching path with observed activity, not evidence that it changed a particular output. |
| GPU compute inventory | target and receiver vLLM engine groups plus a foreign Python GPU process | Neither a single process group nor an exclusive full-device boundary was present. |
| Network publication | target `8000`, receiver `8001`, and ComfyUI `8188` published on `0.0.0.0` and `::` | A public dual-stack bind is not a fresh loopback-only Q1 endpoint. |

The bounded platform digest covers system vendor `MSI`, product `MS-C931`,
product version `5.36_0ACUM024`, OS ID/version `ubuntu`/`24.04`, kernel
`6.17.0-1008-nvidia`, architecture `aarch64`, and Docker server `27.5.1`.
Driver and GPU identities are bound separately. This finite manifest does not
attest firmware, CUDA libraries, model files, or exclusive allocation.

The observed configuration is therefore refused for Q1.  It must not dispatch
Q1 or DNRD-5 calls.  This is an eligibility refusal, not a finding that the
served model is nondeterministic and not a null or positive DNRD-5 result.

The checked-in Q0 forensic result independently records an overlapping subset
of this boundary: prefix caching enabled, `max_num_seqs=6`, another vLLM process
observed, and cross-process provider state not closed.  Q0 remains
`ONE_CALL_CONSUMED_NONCLOSEABLE`; it cannot be repaired, resumed, relabelled, or
used as a Q1 pilot.

## Frontier-AI verdict

The hardware and model family form a high-capacity local-inference
configuration. The informal deployment label "frontier-capable" is not a
scientific class, and three different meanings must not be collapsed:

1. The MSI/NVIDIA GB10 platform supplies a large unified-memory local inference
   envelope. That says nothing about exclusive experimental control.
2. vLLM `0.25.1` satisfies the model card's stated `>=0.19.0` recommendation,
   and the current server enables the Qwen reasoning and tool parsers. This is
   not a compatibility qualification on GB10 or a claim that the deployment is
   state of the art on quality or throughput.
3. NVIDIA's current DGX Spark throughput recipe uses a Qwen3.6-35B NVFP4
   checkpoint with MTP-oriented vLLM optimizations. The observed target is FP8
   without that MTP path. It therefore is not the same throughput-optimized
   recipe. No matched benchmark was run, so no speedup or ranking is inferred.

For Q1, adopting every throughput feature would be scientifically backwards:
batching, speculative or multi-token generation, prefix reuse, and additional
workers can introduce more state and scheduling paths. Such features may be
tested later as separately frozen factors, but the first exactness
qualification should prefer the smallest observable serving boundary.

## Why a scientific configuration may disable throughput features

Serving systems commonly seek throughput through batching, parallel sequences,
prefix reuse, worker scheduling, and network reachability.  A response-exactness
or causal instrument has a different objective: make its finite, declared
intervention boundary observable and falsifiable.  Thus a Q1 configuration may
deliberately sacrifice throughput by requiring one sequence, disabled prefix
cache, a newly started loopback-only provider, a dedicated cache/process/GPU or
node window, and before/after inspection receipts.  These controls can support
only a finite declared boundary; they cannot prove universal absence of
interference.

The Q1 source-stage candidate further requires all 24 constructed request blobs
to be durable before its marker and first START, preserves raw response
envelopes, compares exact assistant-content UTF-8, and treats canonicalized
structured content as diagnostic only.  A caller-supplied isolation receipt,
source digest, or CI digest is not an external attestation.  A future Q1 needs
an independently bound launcher observation before any real dispatch.

The companion read-only instrument in
`_research/dgx_q1/frontier_observer.py` enumerates Docker image and start
identity, a bounded OEM/OS/kernel platform projection, GPU driver identity,
vLLM groups, host listeners, target and foreign GPU cgroups, explicit
revision/cache flags,
batch-invariance environment declaration, and before/after metrics. It permits
only loopback `GET /version`,
`GET /v1/models`, and `GET /metrics`; it has no model
POST path. It deliberately reports that no host-owned lease exists, listener
and metrics PID ownership is unbound, same-cgroup CUDA PIDs are not yet joined
to an allowed worker tree, and an environment declaration is not effective
batch-invariance qualification. Even a fully matched pure snapshot has the
terminal
`Q1_HOST_CONTROL_SNAPSHOT_MATCHED_NONAUTHORIZING`, never dispatch authority.
Its supported checkout invocation is `python -m
_research.dgx_q1.frontier_observer` from the repository root; direct file-path
execution is not the launcher contract.

## Official technical context

- NVIDIA's [DGX Spark user guide](https://docs.nvidia.com/dgx/dgx-spark/dgx-spark.pdf)
  specifies the GB10 Grace Blackwell platform, up to one petaflop of FP4 AI
  performance, 128 GB coherent unified memory, 273 GB/s memory bandwidth, and
  20 Arm cores. Capacity is not exclusive ownership or experimental isolation.
- MSI's [EdgeXpert MS-C931 product page](https://ipc.msi.com/product_detail/Industrial-Computer-Box-PC/AI-Supercomputer/EdgeXpert-MS-C931)
  identifies the OEM product as a GB10/DGX Spark platform. MSI's
  [support page](https://ipc.msi.com/product_download/Industrial-Computer-Box-PC/AI-Supercomputer/EdgeXpert-MS-C931)
  lists OEM OTA releases, including OTA2607 dated 2026-07-27. Any OS, driver, or
  runtime update must be qualified and frozen before a study rather than
  applied mid-occurrence.
- The [Qwen3.6-35B-A3B-FP8 model card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8)
  describes a 35B-total, 3B-active mixture-of-experts model, recommends vLLM
  `>=0.19.0`, documents a native 262,144-token configuration, and gives
  at-least-128K-scale long-context deployment guidance. The observed
  32K setting is a local serving choice, not a model incapacity or a scientific
  result.
- NVIDIA's [2026 DGX Spark optimization report](https://developer.nvidia.com/blog/run-local-ai-agents-with-faster-models-and-multi-node-clustering-on-nvidia-dgx-spark/)
  reports a vendor-measured, configuration-specific gain of up to 2.6 times for
  its Qwen3.6-35B NVFP4 and MTP path. That result does not transfer by assertion
  to the observed FP8 service or to response-exact causal instrumentation.
- vLLM's [reproducibility documentation](https://docs.vllm.ai/en/v0.19.0/usage/reproducibility/)
  says reproducibility is not the default performance setting and limits its
  online guarantee to batch invariance on the same hardware and vLLM version.
  Its [batch-invariance documentation](https://docs.vllm.ai/en/stable/features/batch_invariance/)
  marks the feature beta, requires `VLLM_BATCH_INVARIANT=1`, and does not list
  Qwen3.6 among the documented tested models as of this review. The flag alone
  therefore would not qualify this model/runtime pair.
- vLLM's [metrics documentation](https://docs.vllm.ai/en/stable/design/metrics/)
  exposes prefix-cache queries and hits as counters.  Such counters reveal
  activity, not whether a particular scientific call's output was influenced.

## Frontier research neighbours and falsifiable deltas

These are typed research connections, not evidence that HSWM already has the
claimed property.

| Primary source | What it reports | HSWM bridge and required falsifier |
| --- | --- | --- |
| Behrouz, Zhong, and Mirrokni, [*Titans: Learning to Memorize at Test Time*](https://arxiv.org/abs/2501.00663), first posted 2024-12-31 | A neural long-term memory module that learns to memorize, forget, and retrieve at test time. | FCL-1/FCL-7 architectural neighbour only.  Compare outcome-bound canonical revision against compute-matched frozen retrieval and local test-time-memory controls; falsify the bridge if either control matches the fresh-probe effect or canonical lineage/restore has no additional intervention effect. |
| Yu et al., [*Agentic Memory*](https://arxiv.org/abs/2601.01885), 2026-01-05 | Policy-selected store, retrieve, update, summarize, and discard operations trained with task reward. | A preprint-level FCL-1/FCL-7 bridge: memory operations can be policy actions.  Require sealed operation/readsets plus sham reward, delayed credit, and restore; falsify if shuffled or outcome-independent credit gives the same gain. |
| Parker-Holder et al., [*Genie 3*](https://deepmind.google/blog/genie-3-a-new-frontier-for-world-models/), 2025-08-05 | A real-time interactive generated-world system with limited-horizon consistency and SIMA compatibility tests. | FCL-6 testbed neighbour only.  Test sealed world/self revisions against matched prompt, retrieval, and unchanged-state controls on held-out interventions; falsify if effects do not transfer beyond the generated world or static context matches them. |
| Gallo et al., [*Higher-order modeling of face-to-face interactions*](https://arxiv.org/abs/2406.05026), first posted 2024-06-07, revised 2026-06-30 | Group-interaction modelling that captures properties missed by dyadic models. | Sharpens FCL-3's higher-order bridge.  Compare role-bearing n-ary incidence with degree- and temporal-matched pairwise projections on held-out formation, persistence, and intervention outcomes; falsify if pairwise models match after those controls. |
| Badjatiya et al., [*Leveraging Large Language Models for Effective and Explainable Multi-Agent Credit Assignment*](https://arxiv.org/abs/2502.16863), 2025-02-24 | LLM-assisted multi-agent credit attribution; the credit-assignment problem remains open. | FCL-4 warning, not credit proof.  Blind credit proposers to forbidden arm/outcome data and validate with predeclared counterfactual ablations or difference rewards; falsify if shuffled or outcome-independent credits retain the claimed attribution. |
| Google DeepMind, [*AlphaEvolve*](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/), 2025-05-14 | LLM proposals combined with automated evaluators and evolutionary selection. | A fixed-orchestration baseline for DNRD-5, not an HSWM realization.  Any bounded macro-learning claim must exceed a call-, outcome-, and evaluator-matched fixed search baseline; falsify if the fixed system explains the observed effect. |

## Consequence for the research sequence

The next legitimate step is not to infer an effect from a longer harness or a
more capable frontier model.  It is to obtain a new, isolated, content-addressed
Q1 configuration; freeze its separate plan and marker before any START; close it
independently; and then conduct a separate no-call Source-A audit of the complete
300-block runner, evaluator custody, Permit currentness, randomness, occurrence
judge, and LCB qualification.  Until then, DNRD-5's causal effect is
`NOT_EVALUATED`.
