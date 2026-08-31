# ExpeL B2 text-lesson prior pin

This directory pins an official ExpeL source boundary for the
`B2_EXPEL_INSPIRED_TEXT_LESSON` and `B2_EXPEL_DIRECT` baseline paths. It also
contains a bounded executable two-channel capture closure. It is not a vendored
dependency, full ExpeL or ALFWorld runtime, efficacy experiment, G0
qualification, G1 comparison, or HSWM result.

## What is pinned

[`source_pin.v1.json`](source_pin.v1.json) records the official ExpeL paper
(`arXiv:2308.10144v3`), the official `LeapLabTHU/ExpeL` commit
`e41ec9a24823e7b560c561ab191441b56d9bcefc` and tree
`8ba77f84284693ebbe12ba9a93bd32fd101a6922`, its Apache-2.0 license, and
SHA-256 digests for the versioned paper PDF, observed commit tarball, license,
and the direct-ExpeL algorithm-evidence files: the ExpeL/ReAct/trajectory/retrieval
path, ALFWorld prompt and effective configuration, the actual `RULE_TEMPLATE`,
and the `get_fewshot_max_tokens` source. This is not a runnable dependency or
configuration closure. It intentionally records an immutable
commit because the upstream has no release or tag to pin; the tarball is
accepted only when its observed bytes match the recorded digest.

The official ExpeL path is not lesson-only: it creates a global numbered list
of rules, injects that list through `RULE_TEMPLATE` into evaluation prompts,
and also retrieves successful-trajectory few-shots by similarity. Thus the
lesson-only comparator remains `B2_EXPEL_INSPIRED_TEXT_LESSON`, not a faithful
direct reproduction. `B2_EXPEL_DIRECT` preserves both global rules and
successful-trajectory few-shots. Both paths are external baselines, not HSWM
canonical revisions. Their state is arm-private and cannot authorize HSWM
outcome-credit-owner-`Permit` mutation.

## Required future binding

Before a scientific occurrence, a separate preregistration must bind every
field listed in `future_run_contract.fixed_before_outcome_inspection`, including
the exact prompt bytes, lesson/retrieval policy, split, model/tool surface, and
resource budget. A `B2_EXPEL_DIRECT` preregistration must resolve, rather than
silently choose, the source discrepancy between the paper's cap of 10 rules and
the pinned YAML's `max_num_rules: 20`; it must also make the KNN/FAISS retrieval
and dependency path executable and auditable. It must demonstrate
direct-versus-wrapper parity and B2-only state isolation. The pin deliberately
does not choose those values or select a comparator for an already consumed
occurrence.

The focused offline test validates this record's local schema and digest
invariants. It never fetches upstream resources; re-downloading upstream bytes
is an explicit, separate source-audit action.

The checked-in source-faithful engineering adapter
[`expel_b2_adapter.py`](../../../../src/hswm/experiments/expel_b2_adapter.py)
now verifies the pinned upstream file and license bytes before reconstructing
the two model-visible evaluation channels: numbered global rules and retrieved
successful-trajectory few-shots. The companion
[`check_hswm_expel_b2_adapter.py`](../../../../scripts/check_hswm_expel_b2_adapter.py)
compares exact rule, few-shot, prompt, projected state-write, resource, and
configuration bytes against a pinned-source semantic reference. This closes
only the local source-to-wrapper engineering boundary. The semantic reference
is derived without executing upstream ExpeL, FAISS, a model, or ALFWorld, so it
does not by itself establish direct-runtime parity, baseline efficacy, G0, or
G1.

The [`runtime`](runtime/README.md) closure now pins the exact transitive
dependencies, embedding model revision and files, tokenizer cache, and
synthetic capture fixture. The direct checker executes the pinned upstream
`ExpelAgent` prompt/retrieval methods while a separate wrapper-vector process
that never imports the upstream agent independently executes the embedding,
FAISS, and token-counting inputs. The checked-in
[qualification](../../../../manifests/HSWM_EXPEL_B2_DIRECT_RUNTIME_PARITY_2026-08-31.json)
records exact parity across all eight engineering dimensions. It also captures
the upstream implementation's two physical FAISS index builds. Both processes
were offline and made zero LLM calls and simulator steps. This completes the
two-channel direct-runtime engineering boundary only; an independently owned
outcome/evaluation boundary and any prospective efficacy occurrence remain
open.
