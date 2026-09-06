# B2 text-lesson comparator — prospective draft

> **Status:** `DRAFT_NOT_PREREGISTERED_NOT_FROZEN_NOT_RUN`
>
> **Authority:** `SECONDARY_AI_RESEARCH_DESIGN`
>
> **Claim ceiling:** `NO_RESULT_NO_COMPARATOR_CEILING`

## Role and conceptual delta

This is a design draft for the S-5 secondary B2 ceiling.  It does not alter
the binding G1 estimand: D-3 makes B0 and B2 secondary comparators, while the
primary estimand remains the `project.v1.json` remove/restore, sham,
shuffled-credit, and compiled-mediation rule.  The intended intervention is
only arm-private **external text state**: successful B2 training trajectories
and their simulator outcomes may produce a bounded lesson, and that lesson
may condition later B2 evaluation requests.  It never creates an HSWM atom,
owner decision, Permit, credit, or canonical revision.

This document is deliberately not a result, a source-to-runtime parity claim,
or permission to select a game, inspect an outcome, contact a model, or start
a DGX service.  In particular, no `valid_unseen` UID, path, prompt, episode,
transcript, action, or outcome has been read or selected while making it.

## Selected minimal family

The candidate is `B2_EXPEL_INSPIRED_TEXT_LESSON`, **not**
`B2_EXPEL_DIRECT`.  It uses a global numbered text lesson and deliberately
does not claim ExpeL's successful-trajectory few-shot retrieval channel.  The
direct arm remains a separate project because its full ALFWorld runtime,
training/insight-extraction path, and final direct-runtime parity must be
bound prospectively.

The proposed common surface is the already qualified ALFWorld PDDL-only DGX
environment and Qwen/vLLM identity from the B0 protocol.  The candidate uses
only train and `valid_seen` allocations; `valid_unseen` remains zero-touch.
It is a comparator occurrence and still cannot pass G0 or unlock G1.

## Candidate algorithm (not yet executable)

1. A future sealed selector ranks task groups before games using a new
   occurrence identifier and emits a private receipt plus a public aggregate
   projection.  It allocates training and descriptive `valid_seen` groups
   only, without replacement.  It must not reuse a prior arm's private state
   or inspect `valid_unseen`.
2. On each training episode, the actor receives only that episode's visible
   transcript and observation.  At its terminal, the locally recorded
   simulator outcome is made available to the B2 lesson writer, never to the
   actor during the episode.
3. For a successful training trajectory, the writer creates one numbered,
   bounded natural-language rule using a preregistered reflection prompt and
   deterministic deduplication.  Failed trajectories create no rule.  The
   lesson store, trajectory store, cache namespace, and durable-write root are
   B2-private and are destroyed/reset at the declared boundary.
4. The frozen global lesson is injected as one separately delimited text
   block before every evaluation episode.  The evaluation actor otherwise uses
   the same episode-local transcript discipline and action schema as B0.
5. An outcome scorer emits aggregate split counts and resource accounting; a
   public projection excludes task identities, observations, actions, raw
   prompts, raw lessons, and raw outcomes.  A complete or inconclusive run is
   recorded without retry, replacement, refill, or manual action repair.

The checked-in B2 core is a bounded local state component only. It does not
provide selection, model transport, ALFWorld execution, failure-prefix
preservation, outcome scoring, or a public/private occurrence envelope. This
draft is therefore non-executable as a scientific occurrence.

## Required bindings before freezing

The following list is the complete `future_run_contract.fixed_before_outcome_inspection`
set from the source pin.  `PROPOSED` text is a design preference only;
`PENDING` prevents freezing and execution.

| Required field | Draft binding | State |
|---|---|---|
| `reflection_prompt_bytes_sha256` | A single versioned prompt asks for one general, imperative rule using only the sealed successful visible trajectory and terminal success label; its literal UTF-8 bytes and digest must be checked in. | PENDING |
| `lesson_format_and_deduplication_algorithm` | Numbered one-line printable-ASCII rules; trim boundary whitespace; reject numbering and duplicate rule bytes; retain the first sealed training terminal in committed order. | PROPOSED |
| `maximum_lesson_count` | 10, the paper's reported ALFWorld command cap; at most one retained rule per successful training terminal. | PROPOSED |
| `lesson_token_cap` | 5,120 UTF-8 bytes for rendered lesson state; tokenizer-token cap remains PENDING after exact runtime tokenizer binding. | PENDING |
| `retrieval_embedding_model_and_revision` | `NOT_APPLICABLE_FOR_LESSON_ONLY`; no embedding model or retrieval index. | PROPOSED |
| `retrieval_similarity_metric_and_top_k` | `NOT_APPLICABLE_FOR_LESSON_ONLY`; every retained rule is injected in fixed numbered order. | PROPOSED |
| `retrieval_query_construction` | `NOT_APPLICABLE_FOR_LESSON_ONLY`; no per-episode query. | PROPOSED |
| `direct_arm_rule_cap_and_paper_vs_yaml_resolution` | `NOT_APPLICABLE`: this is explicitly lesson-only and must never be called direct ExpeL. | PROPOSED |
| `global_rule_ordering_and_RULE_TEMPLATE_rendering_bytes` | Training-order numbered rules in a dedicated `B2 LESSONS` delimiter. Exact wrapper UTF-8 bytes and SHA-256 are PENDING. | PENDING |
| `successful_trajectory_fewshot_count_order_ties_and_bytes` | `0`; no successful-trajectory few-shots are injected. | PROPOSED |
| `FAISS_embedding_tokenizer_dependency_versions_and_index_build` | `NOT_APPLICABLE_FOR_LESSON_ONLY`; the action/reflection tokenizer still requires an exact pinned identity. | PENDING |
| `episode_horizon_and_official_vs_common_environment_justification` | Common ALFWorld text-only PDDL path, fresh environment, 20 action maximum; exact B2 training/evaluation allocation is PENDING. | PENDING |
| `official_initial_fewshot_material_fairness_policy` | No initial few-shots in B2 or B0. If an inherited prompt demands one, the B2 run must stop until a common-arm policy is frozen. | PROPOSED |
| `training_holdout_and_final_holdout_split` | Fresh sealed train and descriptive `valid_seen` selection only; `valid_unseen` remains zero-touch. Exact counts, seed/selector version, and whether a final holdout exists are PENDING. | PENDING |
| `base_model_and_revision` | Qwen/Qwen3.6-35B-A3B-FP8 at `95a723d08a9490559dae23d0cff1d9466213d989`; model snapshot manifest and image identity must be reverified immediately before run. | PROPOSED |
| `tool_surface` | ALFWorld PDDL-only worker plus loopback OpenAI-compatible generation endpoint; no retrieval/tool calls. Exact source paths and sandbox identities are PENDING. | PENDING |
| `completion_token_call_retry_time_and_human_minutes_budget` | No retry, replacement, refill, or manual action substitution. Exact allocation of the 240 completion/tokenize ceilings between training, reflection, and evaluation is PENDING. | PENDING |
| `state_reset_and_cache_network_policy` | B2-private lesson/trajectory/cache/output roots; fresh model/cache namespace; no network during episode execution except the declared loopback model endpoint. Exact deletion, preservation, and public-redaction mechanics are PENDING. | PENDING |

## Exact prompt boundary

No task-dependent prompt bytes are supplied in this draft.  The future frozen
registration must check in (1) the constant B2 action system message, (2) the
constant reflection message, (3) the canonical user-payload schema, and (4)
the lesson-wrapper template as separate UTF-8 assets with SHA-256 values.  It
must show that task-dependent values enter only through the permitted
episode-local payload and sealed B2-private training record.  Writing example
tasks, lessons, or trajectories here would violate the no-inspection boundary.

## Implementation readiness and stop condition

`alfworld_b0_actor.py` supplies the bounded one-shot action surface and
`expel_b2_adapter.py` preserves source-level rule/few-shot attribution. The
new `expel_b2_text_lesson.py` core is limited to local outcome-gated lesson
revisions, fresh-root isolation, deterministic rendering/injection, heldout
freeze, and independent request-event accounting. It does not establish a
sealed occurrence or its evidence boundary.

Before a B2 run can be proposed for freezing, implement and locally test:

1. a B2-only selector that proves `valid_unseen` zero-touch and emits private
   and redacted public selection receipts;
2. an arm-private lesson store with outcome-gated writes, deterministic
   normalization/deduplication, reset, and redaction;
3. a one-shot ALFWorld actor that hashes the frozen lesson wrapper and records
   action/reflection/resource budgets;
4. a sealed runner that produces all-run private and public receipts, including
   incomplete terminals, and a separate public posthoc projection/verifier;
5. a preregistration that replaces every `PENDING` cell above with immutable
   bytes, identities, budgets, and a stated comparator ceiling.

Until then the only valid terminal is `DRAFT_NOT_RUN`; there is no B2 result
file, evidence record, or F1_R8 row to create.
