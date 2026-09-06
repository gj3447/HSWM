# D-4 held-out successor — unresolved implementation contract

Status: `DRAFT_NOT_FROZEN_NOT_EXECUTED / D4_V1_NOT_COMPLETE`.
Authority: `SECONDARY_AI_RESEARCH_DESIGN`.

The ratified D-4 milestone requires one checked-in G0-local run linking
independently produced outcome, credit, a durable canonical revision through
the real Atom v2 Permit path, changed held-out behavior, removal,
byte-identical restoration and sham. This draft identifies what an executable
successor still needs. It is not a new experiment or a completion judgment.

## Conceptual delta from opaque v5

The current store is experiment-local. The
[`Atom v2 bridge`](../../../../src/hswm/experiments/atom_v2_permit_bridge.py)
commits an exact transition through the real local Permit process, but its
explicit boundary is `NOT_CANONICAL_HSWM_ADMISSION`. A fsync'd receipt or a new
name for that store does not close D-4's canonical revision requirement.

Likewise, v5's `OPAQUE_ACTION_CODE_DISPOSITION` compiler reads the exact cue
from the same episode. Correct codes are independently derived across
episodes. A different candidate order is another response probe; a new cue
has neither a matching readset nor a declared relation to the learned code.
There is no untouched held-out task evaluation in the v5 result.

A successor therefore needs two substantive changes:

1. a declared study schema, ownership obligations and persistence/commit
   semantics that make the tested revision canonical within the declared
   study, with explicit limits relative to HSWM admission;
2. task-level disposition semantics that apply to genuinely fresh instances
   sharing a prospectively declared relation with training instances.

These are changes to the tested state and task semantics, not a promotion of
v5. The full HSWM target and D-4 success requirements remain unchanged.

## Required implementation before a prospective freeze

| Missing boundary | Concrete implementation obligation |
|---|---|
| Task and holdout | Select a task family and disjoint train/final-heldout partition before content or outcomes are inspected. Define why a learned revision can apply to an unseen instance without containing its answer. |
| Study schema | Declare admitted atom kinds, typed references, immutable version/lineage identity and exactly one responsibility owner per atom. Proposer, evaluator, executor and custodian roles do not automatically determine that owner. |
| Outcome and credit | Seal the emitted trajectory before the separate evaluator returns its outcome. Bind credit to both and verify the proposed revision against that credit. |
| Canonical commit | Bind owner, parent head, schema, transition invariant and actual Permit decision to the same revision bytes. Admit only after successful verification; preserve failed proposals separately. |
| Persistence | Recover the same state in a fresh process. Retain immutable revision and head bytes with a verifiable pre/post chain. A current local Permit slot alone is insufficient. |
| Compiled behavior | Record the revision IDs and compiled bytes used by every held-out call. Keep evaluator material, labels and raw training answers out of the compiler readset. |
| Interventions | ACTIVE, NO_UPDATE, outcome-independent SHAM, SHUFFLED_CREDIT, REMOVE and RESTORE use matched task/runtime/budget surfaces. REMOVE selects the exact pre-revision state; RESTORE selects byte-identical ACTIVE state. |
| All-run accounting | Preserve invalid and aborted prefixes, issued failed calls, costs and terminal status. Never replace or resume a consumed occurrence. |

The candidate schema and task below remain unfrozen and have not been used
for a scientific occurrence. This document does not impose a new fixed
subsystem/owner decomposition or choose an ALFWorld cohort. B0/B2 remain
secondary comparators under D-3.

## Implementation feasibility and current boundary

A bounded study schema can be a candidate D-4 canonical state only when it is
an actual Canonical Atom V2 state, validated under its exact schema and
persisted as the sole authoritative state in one Permit-bound journal. Calling
an opaque gateway post-state `studycanonical` does not by itself make it a
canonical revision or complete D-4.

The feasible route is a D-4 dispatcher which validates a source-bound schema,
full atom state, references, owners, transition invariant, and the content
bytes needed to compile the disposition before it submits one pre/post state
pair to the [V2 verified-admission gateway](../../../../src/hswm/effect-runtime/src/canonical-atom-v2-verified-admission-gateway.ts).
The gateway journal must be the occurrence's single authoritative durable
journal. It must contain the state bytes and the content representation needed
for fresh recovery; descriptors whose bytes live only in a separate store are
insufficient. On a fresh process, the same D-4 validator must recover and
validate that post-state before the compiler receives any disposition.

Do not compose the generic [durable runtime](../../../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.ts)
and gateway as two commits: they have separate journals and a crash can split
Permit consumption from the alleged canonical revision. The generic
[schema/domain validator](../../../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.ts)
provides the schema-relative atom/owner vocabulary, but the gateway currently
treats state bytes as opaque. The dispatcher therefore needs its own D-4
semantic validation on submission and recovery.

The post-state cannot include a permit atom containing its resulting gateway
decision or resulting head digest. Those values depend on the post-state hash,
creating a hash cycle. The enclosing immutable gateway record must bind the
exact Permit decision to the state without such self-reference. The existing
[atomic-admission refinement](../../../../src/hswm/effect-runtime/src/canonical-atom-v2-atomic-admission-refinement.ts)
explicitly leaves outcome support, Permit-at-linearization, exact invariant,
same-transition composition, and runtime mapping `NOT_ESTABLISHED`; this
prospective runtime path cannot claim that formal refinement is complete.

`SECONDARY_AI_RESEARCH_DESIGN` may specify a new bounded schema and its
schema-relative owner obligations; a new human-owner permission is not an
implementation blocker. This does not change S-6: a named independent second
party remains required before any G0-external work. A task notation such as
`F(seed, instance_id)` alone is insufficient: a prospective contract must fix
the generator, actor-visible rendering, evaluator/answer algorithm, split,
and analysis rule.

## Implemented engineering candidate (2026-09-06)

The [task component](../../../../src/hswm/experiments/d4_heldout_task.py)
defines a bounded binary-transform candidate. A valid sealed training action
and binary evaluator result determine a latent XOR bit; fresh instances have
disjoint opaque action identifiers and a new visible action lookup. The
compiler receives only the recovered disposition and fixed task contract.
The 32-row draft schedule balances latent bit, selector, candidate order and
outcome-independent sham. Test fixture seeds are not scientific selections.
This tests a small transferable disposition, not open-ended skill learning.

The [D4 state validator](../../../../src/hswm/effect-runtime/src/canonical-atom-v2-d4-study.ts)
uses actual Canonical Atom V2 schema/state validation for six kinds: task
contract, training instance, sealed trajectory, outcome, credit and
disposition. Exactly one declared responsibility owner applies to each kind.
Every admitted atom's canonical content bytes are inline in the same V2
journal record as its state and exact Lean decision. Recovery revalidates
descriptors, typed references, self-seals, the selected action's decoded bit,
credit arithmetic and compiler binding.

The internal [Node process](../../../../src/hswm/effect-runtime/src/canonical-atom-v2-d4-study-process.ts)
and [Python bridge](../../../../src/hswm/experiments/d4_study_bridge.py) implement
one initial ACTIVE admission and fresh-process recovery. The global state
changes from revision 0 to 1; the new disposition atom is its initial revision
0, bound as `revision:absent → revision:0`. This is not an already-existing
disposition's revision-1 update. The process constructs the fixed atom closure;
it accepts no caller-supplied generic atom mutation. Commit output does not
provide a compiler payload: a separate recovery invocation must return the
validated disposition and identical state/head binding.

Engineering fixtures exercised actual Lean V2 admission, separate Node
recovery, and Python compilation of the recovered bytes. Invalid seals,
owners, extra atoms, repeated commits and wrong occurrence identities are
rejected. These are implementation checks, not a D4 research result. With a
built Node process and Lean CLI, the Python integration command is:

```bash
HSWM_D4_LEAN_EXECUTABLE=/absolute/path/to/HSWMAdmissionKernelCli \
  uv run --locked pytest -q tests/test_hswm_d4_study_bridge.py tests/test_hswm_d4_heldout_task.py
```

The outcome self-seal and credit derivation prove internal consistency only;
they do not establish the truth or independence of an evaluator that can
supply a forged but consistent outcome. A source-bound separate evaluator,
all-call accounting, all six intervention paths, the complete live sequence,
and its prospective freeze remain required. SHAM and SHUFFLED_CREDIT writes
are deliberately unavailable in the current ACTIVE-only process. No held-out
model run has occurred, D-4 remains incomplete, and canonical HSWM admission,
formal runtime refinement, G0-external, G1 and efficacy remain unestablished.

## Success rule and evidence limits

Before a run, freeze sample sizes, margins, denominators, seeds, analysis,
source/runtime identities and stopping rules. The final held-out comparison
must show the preregistered ACTIVE effect, its elimination by REMOVE and
recovery by RESTORE, and failure of SHAM/SHUFFLED_CREDIT to reproduce it.
Every claimed revision must have a reconstructible outcome-to-credit-to-
owner/Permit-to-canonical-state-to-compiled-behavior chain.

Instrument failures remain inconclusive. A valid negative result retires or
reroutes its exact mechanism family with evidence intact. No task, threshold
or denominator may be changed after outcome inspection to produce success.
Meeting D-4 would establish its finite declared milestone only, not
G0-external, G1, general HSWM efficacy or fractal cognitive closure.

The v3/v4/v5 frozen protocols, results and ceilings remain unchanged. This
unexecuted draft creates no research receipt, F1_R8 result or KG event.
