# ALFWorld B0 prospective calibration

This preregistration freezes one no-learning ALFWorld calibration before any
B0 task selection, ALFWorld episode, or task outcome. Its sole purpose is to determine
whether the pinned task/model surface has usable headroom and whether the
sealed measurement path fails under realistic interaction. It is not a G0
pass, G1 occurrence, comparator result, HSWM revision, or efficacy claim.

The initially checked-in protocol SHA-256 was
`6d1f18f3ccc0e70ed8b4ba72a98462114fe647f26e7e19919fc3c1ecb072249d`.
Before any B0 selection, ALFWorld episode, model call, or outcome observation,
a DGX dependency-build attempt showed that TextWorld's normal setup requires
an Inform7 compiler payload unavailable for `aarch64`. The machine-readable
`prospective_amendments` record preserves that chronology and binds the
PDDL-only adapter below. It is an environment amendment, not a result-driven
change to allocation, estimands, thresholds, or stopping rules.

Subsequent fixed-action engineering qualification reached the sandbox launch
but stopped before its first actor frame because the DGX AppArmor policy
rejects the required unprivileged user namespace. No B0 selection, model call,
or B0 outcome had occurred. A reset-only diagnostic then established the exact
B0-specific adapter: noninteractive `sudo` plus Bubblewrap with explicit
PID/IPC/UTS/network namespaces, best-effort cgroup namespace isolation, no user
namespace, and all capabilities dropped except `CAP_DAC_READ_SEARCH`. The
controller hashes and holds the selected game FD, exposes its `/proc` FD path
as a read-only bind, and the worker hashes the mounted bytes again. The
historical runtime remains unchanged.

That adapter is trusted-maintainer local engineering containment. It is not a
hostile-local-user security boundary or an independent evaluator, and its
reset-only diagnostic is not a B0 episode, G0 evidence, or HSWM efficacy.

A later pre-selection counter-semantics probe issued one neutral tokenize
request and one tiny schema-constrained completion on a fresh service, but its
aggregate projection rejected the expected fixed ALFWorld source-path labels
and wrote no qualification receipt. We did not inspect a counter delta from
that failed occurrence. The prospective repair permits those committed source
labels, keeps task identities and raw request/response evidence forbidden, and
moves root-owned container caches outside published outputs. The repeat uses a
new occurrence identifier and remains separate from every ALFWorld episode and
task outcome.

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
The inherited cross-platform package reference remains
[`alfworld_text_runtime.requirements.v1.txt`](alfworld_text_runtime.requirements.v1.txt).
The ARM64 occurrence instead installs the exact
[`alfworld_text_runtime.arm64_pddl_only.requirements.v1.txt`](alfworld_text_runtime.arm64_pddl_only.requirements.v1.txt),
which differs only by omitting `textworld==1.7.0`. It then installs the
official [TextWorld 1.7.0 tag](https://github.com/microsoft/TextWorld/releases/tag/1.7.0)
at `9fce9ee107fa042ef2656e41e0b362450a35ecd8`, after checking and applying
[`textworld-pddl-only.v1.patch`](textworld-pddl-only.v1.patch), with
`TEXTWORLD_PDDL_ONLY=1` and `--no-deps`. The patch preserves upstream default
installation and only causes each upstream build/install/develop hook to skip
its Inform7 setup when that explicit variable is set. This is valid only for
ALFWorld's PDDL path: upstream lists
[`fast-downward-textworld`](https://github.com/microsoft/TextWorld/blob/9fce9ee107fa042ef2656e41e0b362450a35ecd8/requirements-pddl.txt)
for `PddlEnv`, while its
[`setup.py`](https://github.com/microsoft/TextWorld/blob/9fce9ee107fa042ef2656e41e0b362450a35ecd8/setup.py)
normally invokes `setup.sh` from all three hooks. This occurrence has no
Inform7 capability. The upstream `aaba6870` ALFWorld source is installed next
with `--no-deps`; HSWM code remains bound to the clean execution checkout.

Even a complete run cannot pass G0. The simulator outcome is hidden from the
actor, but it is still a local, same-stack boundary with no independent owner
or evaluator swap, and an independent live known-answer calibration is still
absent. A complete run can only yield
`EXPLORATORY_B0_CALIBRATION_COMPLETE_G0_NOT_PASSED` plus one operational
headroom class. The exact machine-readable authority is
[`protocol.v1.json`](protocol.v1.json).
