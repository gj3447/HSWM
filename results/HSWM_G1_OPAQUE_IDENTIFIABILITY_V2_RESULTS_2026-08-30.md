# HSWM opaque-action identifiability v2 result

## Result

The frozen eight-episode DGX occurrence reached the preregistered terminal
`PILOT_COMPLETE_IDENTIFIABILITY_OBSERVED_NO_EFFICACY_INFERENCE`.

The bounded local instrument produced a discriminating state-mediated
behavioral signature: ACTIVE and RESTORE were correct in 8/8 episodes,
FORCED_OPPOSITE_FEEDBACK was correct in 0/8, and NO_UPDATE and REMOVE were each
correct in 4/8. The primary descriptive estimand was
`delta_state = 2/3`, above the preregistered exploratory threshold `7/12`.
Credit and admission occurred exactly eight times in each updating branch, and
REMOVE/RESTORE returned to the required states in all eight episodes.

This is the first observation from this instrument in which a locally admitted
revision, its compiled readset, removal, and restoration separate fresh
behavior from no-state controls. It is an **exploratory G0 identifiability
result**. It is not a G0 gate pass, a G1 efficacy result, evidence that HSWM
outperforms a reused baseline, or evidence of canonical HSWM learning.

The public aggregate projection has SHA-256
`afc7e1f56522f276376ef7f331962f737b4ff2eeda1dff10f6ebc3fa35232f65`.
The evaluator secrets, per-episode target mappings, raw requests and responses,
state stores, journals, and private infrastructure observations remain in the
content-addressed durable closure and are not published.

## Frozen occurrence

- Study UID:
  `sym:ExploratoryStudy:hswm-g1-opaque-identifiability-v2-2026-08-30`
- Protocol canonical SHA-256:
  `eae768f3f42de345bfcc995a5effb085f39c1732bb956fa37c6eab08870a553d`
- Protocol file SHA-256:
  `a5981cdfff9fc35447933ca6662f0e92d07a436f49319427e05454926aeb907f`
- Execution source commit:
  `31a003564f078e0f9ba419f1d1cabcbecd89c684`
- Source tree:
  `1dae290caab8bc8e392f686150040f35c5a9c3fb`
- Source CI: run `33316526514`, all eight jobs successful
- Live wrapper run: `g1-opaque-identifiability-v2-31a0035-v1`
- Live interval: `2026-08-30T14:32:50Z` to `2026-08-30T14:41:48Z`
- Model: `Qwen/Qwen3.6-35B-A3B-FP8`, revision
  `95a723d08a9490559dae23d0cff1d9466213d989`
- Runtime: vLLM `0.25.1`, NVIDIA GB10
  `GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5`
- Container image:
  `vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089`
- Calls: 64 completions and 64 tokenizer preflights, all completed in the
  frozen order with no retry or refill
- Registry terminal: `COMPLETED_NO_RERUN`

Before the one-shot occurrence, wrapper run
`g1-opaque-v2-preflight-31a0035-v1` reproduced the offline tokenizer receipt
with no behavioral network call and no shared-service mutation. Its receipt
SHA-256 is
`e8b4f2e2ae795d798841daf06493c4617290457b13e7701ca9e3a129a664d91f`.

The execution wrapper receipt has SHA-256
`4e4f5f5f58321502b34bdb5a74138edb8490233525d17b5042fc780d7c502bdf`.
Its private 3,184,640-byte archive has SHA-256
`a3d0093e23eccd6a3cce2c751077eaaf5f0288e9021675c7b1b3a695b91cf876`.
The durable registry SHA-256 is
`408e8606eb01e12db6f7c885099baf07c523f1309c9607ec54ee0b0c6fc2f7e4`,
and the internal result bundle digest is
`9df2cb715b526ce87b072ca2898dde49959fc71e282761e0f074c9e38ce19a08`.

## Aggregate observation

| Branch | Correct | Wilson 95% interval |
|---|---:|---:|
| ACTIVE | 8/8 | `[0.6756, 1.0000]` |
| FORCED_OPPOSITE_FEEDBACK | 0/8 | `[0.0000, 0.3244]` |
| NO_UPDATE | 4/8 | `[0.2152, 0.7848]` |
| REMOVE | 4/8 | `[0.2152, 0.7848]` |
| RESTORE | 8/8 | `[0.6756, 1.0000]` |

The preregistered descriptive checks all held:

- `delta_state = 0.6666666666666667 >= 0.5833333333333333`;
- ACTIVE and RESTORE were 8/8, and FORCED_OPPOSITE_FEEDBACK was 0/8;
- NO_UPDATE and REMOVE were each 4/8, below their maximum 5/8;
- combined no-state correctness was 8/16, below its maximum 10/16;
- ACTIVE and FORCED_OPPOSITE_FEEDBACK each closed eight credit/admission
  traversals;
- exact remove/restore closed in 8/8 episodes.

The descriptive contrasts were ACTIVE minus FORCED_OPPOSITE_FEEDBACK `1.0`,
ACTIVE minus the mean of NO_UPDATE and REMOVE `0.5`, and RESTORE minus REMOVE
`0.5`.

## What the result identifies

The model-visible task used episode-secret opaque action codes. The evaluator
alone held the target mapping, and the sealing checks found no target mapping,
evaluator secret, legacy arithmetic operator, operand, value-derived label, or
branch label in a model request. This removes the value leakage that saturated
the predecessor micro task.

Within this instrument, the admitted ACTIVE disposition was deterministically
compiled into the fresh-probe readset. The outcome-dependent counterfactual
branch admitted the opposite disposition. Removing the ACTIVE state returned
to genesis; restoring it returned to the exact ACTIVE snapshot. The resulting
ACTIVE/forced-opposite and RESTORE/REMOVE contrasts therefore identify that the
bounded local state was read by, and could change, the fresh action in this
task.

That is a mechanics-and-identifiability finding. The local grant is not an
Atom v2 Permit, the local state is not repository-canonical HSWM admission, and
the same-process evaluator is not independently owned G0 or CF-07 evidence.
The occurrence does not establish that an HSWM learned a generally useful rule
from an independent environment outcome.

## Position sentinel and full-pattern caveat

NO_UPDATE and REMOVE were correct 4/4 when the target happened to be the first
candidate and 0/4 when it was second. The two no-state branches therefore show
a deterministic first-candidate bias, not independent 50% sampling. Their
candidate orders were complementary by design, so the strict per-episode
five-branch signature count was 0 even though the aggregate preregistered
identifiability rule was observed.

This is an important limitation, not a reason to relabel the terminal. It
shows exactly why the current evidence supports only a bounded state-readout
claim. A confirmatory study needs a design and analysis that does not mistake
candidate-position behavior for a reusable learned effect.

## Independent structural verification

A separate frozen-source DGX wrapper run,
`g1-opaque-v2-verify-31a0035-v1`, returned:

- `VALID_LOCAL_OPAQUE_PROTOCOL_REVEAL_REGISTRY_BINDING`;
- `VALID_LOCAL_DGX_FINAL_ATTESTATION_AND_RESTORATION_JOIN`;
- `VALID_LOCAL_FROZEN_DGX_EXPLORATORY_EXECUTION`.

Its wrapper receipt SHA-256 is
`3c43ee432644dd8294e6320752170208bdced98fdc42df368dc1dfb19b6f13d0`;
the 10,240-byte wrapper archive SHA-256 is
`44f158ee43fa48bf8451c4a00c7ffc179278110269cfc4ad9e366461e39c45c9`.
The checked-in 982-byte aggregate verifier output has SHA-256
`fba4b80c6d54a53e58e4e3c75febaeb054a648c6e884623f7d989584357a588b`.

A separate private read-only byte audit recomputed the protocol and reveal
commitments, registry and record hashes, result bundle digest, all 64
completion and 64 tokenizer call sequences, 512 journal events, every episode
state transition, and all 63 files in the private wrapper archive. It found no
result-invalidating discrepancy. That supporting audit has no separate public
receipt and is not an additional evidence-bearing occurrence. The published
frozen verifier output above is the public structural verification record; it
is not an independently owned scientific outcome judge.

## Reuse-first boundary

This occurrence intentionally tested only the HSWM-specific causal variable:
sealed outcome-to-credit-to-local-revision, deterministic compilation into a
behavioral readset, and remove/restore lineage. It did not run the B0-B3
memory, lesson, skill-library, or metagraph comparators defined by the
[reuse-first architecture](../docs/research/HSWM_REUSE_FIRST_ARCHITECTURE_2026-08-30.md).

Consequently, it makes no comparative claim about Letta/MemGPT, Reflexion,
ExpeL, ACE, Voyager, Hyperon/AtomSpace, or any other inherited system. The
confirmatory G1 preregistration must choose one strongest primary comparator in
advance, bind a paired primary estimand and threshold, and classify the other
comparators as secondary with an explicit multiplicity policy. “Better than
the strongest inherited baseline” is not yet an executable decision rule.

## Privacy and evidence boundary

The raw archive is retained on private durable storage. It is not checked into
the public repository because it contains the evaluator answer key and
commitment preimages, raw model traffic, per-episode state databases and
journals, and host/network/process/storage observations. Publishing those
bytes would weaken future task secrecy and disclose private infrastructure.

The public projection contains aggregate counts, preregistered thresholds,
nonsecret runtime identity, and exact content hashes that bind it to the
private closure. The separate verifier output is safe to publish because it
contains only aggregate digests and validation labels.

## Scientific boundary and next experiment

The formal status is:

- claim ceiling: `EXPLORATORY_G0_IDENTIFIABILITY_ONLY`;
- G0: identifiability threshold observed, gate not passed;
- G1: `NOT_EVALUATED`;
- G2-G6: locked;
- HSWM learning efficacy: not established;
- reuse-first baseline comparison: not run;
- canonical HSWM revision or Atom v2 Permit: not performed.

The next scientific step is not a rerun of this consumed occurrence. It is a
fresh preregistration with an independently owned outcome/evaluation boundary,
a genuine outcome-independent sham, one task family, one revision kind, one
admission path, a preselected primary reuse-first comparator, and a powered
paired estimand. Only after G0 measurement integrity is complete should that
minimal confirmatory G1 be executed.

This result does not test or change the eight FCL laws, HSWM-of-HSWMs same-rule
recursive composition, consciousness, selfhood, or scale-invariant causal
closure. The fractal research status remains
`SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`, and the live KG is not
mutated.
