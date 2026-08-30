# ALFWorld B0 prospective calibration

This preregistration freezes one no-learning ALFWorld calibration before any
B0 environment, model, or outcome call. Its sole purpose is to determine
whether the pinned task/model surface has usable headroom and whether the
sealed measurement path fails under realistic interaction. It is not a G0
pass, G1 occurrence, comparator result, HSWM revision, or efficacy claim.

The sole arm is `B0_STATELESS_NO_LEARNING`. Each model call is a fresh
one-shot request. It may read the bounded visible transcript from the current
episode, because ALFWorld is partially observable, but that transcript is
discarded at terminal and is never carried into another episode. The arm has
no lesson, retrieval, successful-trajectory few-shot, expert command list,
cross-episode memory, credit, revision, owner decision, or `Permit`.

The deterministic private selector ranks task groups before games and commits
eight train groups plus four `valid_seen` groups, one game per group. The
`valid_seen` sample is descriptive only: 25 of its 27 groups overlap the
official train split. All 11 zero-overlap `valid_unseen` groups remain
untouched—no selection, model call, prompt work, transcript review, outcome
inspection, or threshold tuning.

The environment itself terminates at 20 model actions. There are no synthetic
tail actions. Every scheduled episode is fresh and receives no retry,
replacement, refill, human repair, or hidden parser repair. Any integrity or
transport failure seals the exact attempted prefix and ends the occurrence as
`INCONCLUSIVE_MEASUREMENT_NOT_READY`.

The model/runtime identity reuses the already measured Qwen3.6-35B-A3B-FP8
revision, vLLM 0.25.1 image, NVIDIA GB10, loopback service, strict JSON schema,
single-sequence scheduling, disabled prefix cache, disabled async scheduling,
and disabled thinking. The official
[Qwen model card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8/blob/95a723d08a9490559dae23d0cff1d9466213d989/README.md)
documents the explicit thinking switch, and the version-matched
[vLLM engine reference](https://docs.vllm.ai/en/v0.25.1/configuration/engine_args/)
documents the reused scheduling and cache controls. Greedy decoding reduces a
known noise source but byte-identical provider output is not a prerequisite.
The ALFWorld process reuses the already qualified package versions from
[`alfworld_text_runtime.requirements.v1.txt`](alfworld_text_runtime.requirements.v1.txt);
the upstream `aaba6870` source is installed separately and HSWM code remains
bound to the clean execution checkout.

Even a complete run cannot pass G0. The simulator outcome is hidden from the
actor, but it is still a local, same-stack boundary with no independent owner
or evaluator swap, and an independent live known-answer calibration is still
absent. A complete run can only yield
`EXPLORATORY_B0_CALIBRATION_COMPLETE_G0_NOT_PASSED` plus one operational
headroom class. The exact machine-readable authority is
[`protocol.v1.json`](protocol.v1.json).
