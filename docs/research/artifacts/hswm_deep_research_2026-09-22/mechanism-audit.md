# JEV local semantic execution and revision mechanism audit

**Date:** 2026-09-22
**Scope:** forensic, read-only audit of the 2026-09-21 sealed JEV-principles run and its source-pinned execution path.
**Status:** `INSTRUMENT_AND_MECHANISM_AUDIT`; it neither establishes HSWM efficacy nor changes any CR/FCL status.

## Decisive result

The run does demonstrate durable, mechanically admitted *revision occurrences*, but it does **not** identify whether a revised semantic relation improves later execution.  For all four families, the post-run audit found no difference in any visible semantic field (`semanticText`, `disposition`, `uncertainty`, `exceptionRefs`), and the learned and evidence-only evaluation inputs are byte-identical.  Thus the learned/evidence-only score difference cannot be assigned to a visible semantic-revision effect; it is compatible with the separately observed serving variation.  An identity revision is a legitimate first-class outcome: semantic text change is neither necessary nor sufficient for semantic improvement.  Here it is non-identifying because the protocol contains no separately measured disposition or behavior change attributable to the admitted identity revision.

The direct oracle result is 27/48, not an oracle-execution ceiling.  It is a frozen-model, one-token `0`/`1` conditional-logprob readout under an oracle-written natural-language rule.  No symbolic evaluator, trained classifier head, or execution compiler is present.  Therefore it answers the narrow question “can this serving configuration turn this prompt into a next-token binary decision?” and fails that question on 21 cases.  It does not show that the graph lacks the correct relation: its oracle semantic text explicitly includes the missing `pel` context flip.

The appropriate next gate is consequently **local semantic execution fidelity before further topology, parallelism, scale, or causal-credit work**.  A later learning study needs a predeclared, read-back-visible state/disposition witness that can be causally compared with controls while keeping the outcome split blind.  That witness can be a semantic-text change, but need not be; text change alone would not establish improvement.

## What the recorded task requires

The generated label is `base(family, dax, wug, zif) XOR pel XOR nub`.  The initial relation deliberately says that `pel` has no effect; the oracle relation states that `pel=1` flips the base bit, and both state that `nub=1` flips it.  So even the oracle requires binding the case’s subject fields, context field, and exception field, interpreting a natural-language relation, then composing two flips.  This is a useful local semantic-operator test, but only 32 finite authored bit patterns and four rule families exist.

The evaluation projection serializes the relation text, disposition, exception references, uncertainty, all role contents, the most recent prior observation, and the current single case as JSON.  Role membership and ordering are retained in the runtime frame; the JEV wrapper passes those role records straight into `roleContract`.  The LLM receives no separately rendered, typed execution program or field-to-role binding beyond those JSON names and descriptions.  That is an intentional semantic-reading condition, but it leaves a prompt-following/compositional-execution bottleneck that an oracle relation alone cannot remove.

## Confirmed mechanism findings

| Finding | Evidence | Consequence |
|---|---|---|
| Semantic learning did not mediate later evaluation. | All four `changed_semantic_fields` arrays are empty and `learned_equals_evidence_only_visible_input` is true in the sealed audit. | Do not interpret learned-versus-evidence-only numbers as a learning effect. |
| The revision API can carry a changed proposal and also accepts identity revisions. | The runtime validates shape and exact exception references, then constructs the successor directly from the LLM proposal; it has no non-identity or held-out-improvement criterion. | Identity is not a generic runtime defect.  The study needs a declared `NO_SEMANTIC_DELTA` result class and a separate state/disposition witness before it can estimate a revision effect. |
| Training is one batched prediction followed by one batched outcome and one learning call. | The worker predicts 12 training cases as one concatenated bit string, attaches all labels in one outcome, then invokes one revision. | This is a limited one-shot rule-induction study design.  It does not assess per-example online credit assignment, trajectory comparison, or sequential revision effects. |
| Oracle text remains an LLM interpretation task. | The oracle arm only seeds the corrected string, then the JEV runner bypasses `executeLlmSemanticRelation` and requests direct/generative readout from the model. | 27/48 is an execution-readout result, never a representation oracle. |
| Direct and generated modes have different output contracts. | Direct mode has `max_tokens:1`, candidate IDs `[15,16]`, and parses top logprobs; generated mode has 96 output tokens, JSON Schema, and self-reported `p1`. | Their score gap cannot isolate “generation versus direct readout” without a shared decision semantics. |
| Generated mode has a contract-validity, not only accuracy, problem. | Only 389/480 calls were valid overall; the reject reason is `PREDICTION_PROBABILITY_DISAGREEMENT`. | Refusal is correctly counted as wrong by protocol, but it confounds semantic execution with the model’s ability to report a consistent probability. |
| Determinism was not obtained empirically. | Sealed audit records byte-identical requests with changed prediction objects, and one paired-valid learned/evidence-only direct test-bit change in family 2, despite `temperature:0` and `seed:0`. | Paired arm deltas need replicated scheduled calls and a serving determinism diagnosis; seed and temperature are not evidence of determinism. |

## Why 27/48 can arise

These mechanisms are code-confirmed contributors; their quantitative share cannot be inferred without the private request/response corpus or a new controlled run.

1. **Execution has not been separated from language-model next-token preference.** Direct mode constrains output to two token IDs and derives `p1` only from their relative log odds.  This is a readout of the frozen model’s next-token distribution, not an executor of the oracle relation.  The correct relation may be present in context while the next-token preference remains wrong.
2. **The prompt carries a composition task.** Each answer needs base-rule interpretation plus `pel` and `nub` flips.  `roleContract` is JSON data, and the system instruction merely tells the model to respect roles/context/exceptions.  No deterministic checker turns those role contracts into a computation.
3. **Candidate-token semantics are narrower than a binary classifier.** `p1` is normalized between reported `0` and `1` logprobs.  The recorded `candidateMass` is usually high but can be as low as 0.0396; the code itself labels this conditional candidate probability rather than a full-vocabulary probability.  If the server applies `allowed_token_ids` before logprob reporting, the mass interpretation changes; this audit has no source-pinned serving implementation or tokenizer proof to decide that question.
4. **One-token direct output permits no written reasoning or self-correction.** This is a legitimate cheap-readout condition, but it is a stricter capability test than a relation-execution path that permits an internal scratch computation.  It cannot be called the whole LLM-function operator result.  The audit does not show that the one-token limit caused any error; that is a testable hypothesis.
5. **Serving behavior varied under nominally deterministic parameters.** That directly threatens single-observation causal comparisons, though the audit cannot identify whether batching, kernel selection, server scheduling, model configuration, or another serving detail caused it.

## Revision no-op: causal chain

The source-pinned worker seeds an initial graph, asks the model once to predict all 12 training cases, stages one outcome containing every observed label, and asks once for a concise revised relation.  The generic runtime returns the LLM proposal after structural validation.  The recorded admission is `COMMITTED` for every family, but the sealed audit finds the four semantically visible fields unchanged.  The evidence-only control then copies the durable learned state and restores those same fields to the initial strings.  Since they were already unchanged, its evaluation projection is identical to learned.

This means the no-op is **not** merely a metric artifact: it is confirmed in the canonical states and prompt projection.  It is not, by itself, an error: retaining the same semantic text can be the correct outcome if the prior relation is already adequate, and changed text can be semantically irrelevant or harmful.  The remaining unknown is why the model proposed identity text in this setting: insufficient training signal, a prompt that does not demand an explicit delta, the model’s own incorrect training prediction, adequate preservation of an already useful rule, inadequate rule induction, or an uninspected constrained-generation effect are all hypotheses.  The audit contains no private response bytes and does not select among them.

## Instrument defects versus open hypotheses

| Classification | Item | What would resolve it |
|---|---|---|
| Confirmed study-design limitation | Identity revisions are admitted and the report labels the arm `learned`, but there is no declared `NO_SEMANTIC_DELTA` result class or independent state/disposition witness. | Preserve identity as a valid outcome; classify it explicitly, and make revision-effect analysis conditional on a predeclared, read-back-visible causal contrast. |
| Confirmed study-design limitation | Direct and generated arms implement different decision channels and generated validity depends on self-reported probability consistency. | Use one shared decision extraction method or report semantic execution, output conformance, and calibration as separate endpoints. |
| Confirmed study-design limitation | A single model call sees all 12 labels in one outcome; no per-example update or independently measured holdout state/disposition witness exists. | Explicitly name this one-shot rule-induction condition; add an outcome sequence only when testing online learning. |
| Confirmed observation, cause unknown | Identical requests yielded changed outputs at zero temperature and seed. | Log server/version/tokenizer/configuration identifiers and run fixed-prompt repeat blocks before arm comparisons. |
| Hypothesis | Hard-coded IDs 15/16 represent the intended standalone `0`/`1` tokens under the exact chat template. | Pin tokenizer revision and run tokenizer + response-token audit, including leading-space/newline alternatives. |
| Hypothesis | `allowed_token_ids` changes server logprob normalization, making candidate mass incomparable to an unmasked distribution. | Pin the exact serving implementation/version and run an unmasked-logprob versus masked-logprob probe with identical prompts. |
| Hypothesis | The model needed an intermediate computation, more output budget, or a different execution/readout contract. | Hold information fixed; compare direct one-token, typed intermediate execution with separately extracted bit, and deterministic symbolic execution only as a representation upper bound.  Treat changed compute/token budget as an explicit cost factor, not a matched-cost claim. |

## Minimal next executable slice

Do not run another learning or scaling study first.  The smallest discriminating slice is a four-condition, replicated **local semantic execution gate** on the same four task families:

1. Pin and record checkpoint, tokenizer, chat template, server version/configuration, precision, and deterministic-serving settings.  Run 20 repeats for each fixed request and report bit/probability stability before scoring arms.  Twenty is a proposed diagnostic replication count, not a power guarantee.
2. Freeze one oracle graph and evaluate: (A) current one-token direct readout; (B) generated answer with the bit extracted from the answer only, without a self-reported `p1` validity gate; (C) structured two-stage model execution whose first stage returns a typed intermediate evaluation record and whose second stage maps that record to a bit; and (D) a non-LLM reference evaluator derived from the authored rule solely to validate task/serialization.  (D) is a task-fixture ceiling, not HSWM evidence.
3. A–C must receive equal canonical information: same relation, role order, case, and label-blind evaluation split.  Fully account for prompt, completion, and intermediate-stage tokens, latency, calls, and hardware/service configuration.  A compute-budget difference is an explicit experimental factor; do not claim matched cost merely because graph information is equal.
4. Gate progression: treat above-chance or balanced-0.5 performance only as a diagnostic.  Before learning work, require near-perfect finite oracle truth-table census and stable behavior under predeclared semantic paraphrases and role-order/permutation tests that preserve the typed relation.  If this condition fails, stop semantic-learning/topology work and repair local execution/readout.  If it passes, run a separate learning test with a predeclared read-back-visible state/disposition witness, a causal control contrast, and a hidden evaluation suffix against frozen and evidence-only controls.

The gate tests CR-0’s bounded local output contract only.  It supplies no causal credit, real-world validity, Hyperon comparison result, CR-1..7 closure, or FCL-1..8 closure.

## Source and evidence binding

All line references use the listed bytes.  The run’s own source-pins file reports no repository commit (`repository_commit: null`), so this audit binds the working-tree source hashes and sealed public artifacts rather than asserting a reproducible service binary.

| Path | SHA-256 | Lines used |
|---|---|---|
| `_research/jev_principles_v1/domain.mts` | `987aa6952e20e5033267df14df7d16e9008054bf359a06064978c05b0998a21f` | 3–38 |
| `_research/jev_principles_v1/run.mts` | `dd383ec81025b4d3cfccba256c12be54044f3f251b06e028d9857119116c1018` | 24–65 |
| `_research/jev_principles_v1/analyze.mts` | `820bf5758c39c7a27bdc6033db34c6ed3e91502acf017e11bece625b27a567a3` | 13–48 |
| `_research/jev_principles_v1/audit.mts` | `f45d7c240045c3b47fb45c7c586c490116c6d5d444d6924867992e0cd210e98d` | 24–48 |
| `_research/jev_principles_v1/support/domain.mts` | `92f9bfff8a163f6d243a03e7ddc0c61ab2a56eae015d4355d06f7a4b3ad2860a` | 5–32, 49–66 |
| `_research/jev_principles_v1/support/run.mts` | `6adfbacab537dfdc14b4b02e72114c7f0a1b748633a0983ba52c85ee75585091` | 32–35, 120–180, 193–231 |
| `_research/jev_principles_v1/store.mts` | `65922c842a16f78b0775455d178f6fac1b82394b7c2c33780b4cf0778c693681` | 90–105 |
| `_research/jev_principles_v1/source-pins.v1.json` | `6465e5367c451e568e025e4fc99f9fc0577e3cf5ae3dbcc1b2013c552ec4195c` | metadata and source bindings |
| `src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.ts` | `a2302c05c058c855e21cba709e5b90f8e9336534d42c18a347e28f8c0977a1a0` | 59–78, 136–174, 177–207, 218–283 |
| `src/hswm/effect-runtime/src/semantic-decision-domain.ts` | `5849a88550941f4b8f1e4406cb54d78446a54535f6e505581975b4181d5691b4` | 17–42, 45–73 |
| `docs/research/artifacts/hswm_jev_principles_2026-09-21/observations.v1.json` | `6d2e587235986c632bf0b7cf5949d1f5d33d4267ae39267848900d812b401123` | oracle and arm summaries; completion |
| `docs/research/artifacts/hswm_jev_principles_2026-09-21/audit.v1.json` | `00be273a1c4467627a2fc5cfb316dad74599c5692965c7650b04bce7936d1e92` | family no-op and repeated-request diagnostics |

The separately present `relation_synthesis` and local-process working-tree changes were inspected only for scope.  They change source-pin/CLI-local-process work and have no evidence connection to the sealed JEV run, so this audit makes no claim about them.
