# HSWM TypeScript-to-Lean refinement obstruction

> **Status:** `SECONDARY_AI_FORMAL_REFINEMENT_BOUNDARY / POSITIVE_REFINEMENT_BLOCKED / SCIENTIFIC_UNJUDGED`
>
> **Lean sources:**
> [`HSWMCanonicalLearning.lean`](../../formal/HSWMCanonicalLearning.lean)
> and
> [`HSWMTypeScriptV1Refinement.lean`](../../formal/HSWMTypeScriptV1Refinement.lean)
>
> **TypeScript sources:**
> [`canonical-atom-v2-transition-evidence.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-transition-evidence.ts)
> and
> [`canonical-atom-v2-current-state-permit.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-current-state-permit.ts)
> with the fail-closed projection in
> [`canonical-atom-v2-learning-refinement.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-learning-refinement.ts)

## 1. Canonical role and reason for this boundary

HSWM remains one token-native LLM-function macro-neural process. Its evolving
schema-relative hypergraph is the same object's living harness, world model and
continuous learner. The TypeScript modules named above are bounded projections
and evidence interfaces to that state; they are not separate cognition,
routing, authority or learning subsystems.

The preceding Lean boundary proved necessary conditions for a canonical
`Learn` transition. The next question is not whether TypeScript values have
similarly named fields. It is whether the exact checked-in TypeScript semantics
can soundly provide every Lean admission witness without changing the meaning
of any status literal.

They cannot yet do so. Recording that obstruction is the correct refinement
result. Relabeling local eligibility as canonical Permit or an observed outcome
as support for a revision would weaken the proof boundary and contradict the
existing byte contracts.

## 2. Conceptual delta

This phase adds a negative refinement profile between two already existing
layers:

```text
validated TypeScript v1 bytes
  -> exact semantic-status projection
  -> Lean admission-obligation profile
  -> BLOCKED_NOT_REFINED_TO_LEAN_LEARN
```

It does not connect the current reducer to outcome learning. It establishes
which correspondences are structurally available and which semantic witnesses
are absent. The fixed `H/W/A/F/Pi` decomposition is not used.

## 3. Field and meaning map

| Lean boundary | Current TypeScript projection | Refinement status |
| --- | --- | --- |
| schema-relative atom address | `schemaVersion`, `lineageId`, `atomUid` in an exact key | structurally representable |
| immutable atom revision | numeric `revisionId` | representable, but the Permit input does not establish the Lean boundary's one-target current-revision transition for every multi-write proposal |
| pre-outcome trace binding | exact proposal, trajectory, trace key and content descriptors | structurally represented and validated; real publication chronology remains unproved |
| actor/proposer | `actorClaim` | representable for a bounded projection |
| evaluator role | outcome `evaluator` plus optional declared role separation | represented; social or statistical independence is not proved |
| outcome responsibility owner | no dedicated outcome-receipt responsibility-owner field | missing |
| outcome supports the candidate revision | `OBSERVED`, `FAILED`, or `UNKNOWN`, always `REPRESENTED_NOT_CAUSAL_CREDIT` | missing |
| current canonical Permit | local eligibility explicitly ending in `NOT_CANONICAL_PERMIT` | missing |
| schema-relative invariant witness | no value proving `Inv(S,c)` | missing |
| atomic canonical admission | read-only eligibility has no commit capability and says `NOT_ADMITTED_BY_THIS_RESOLUTION` | missing |

The address and descriptor similarities are therefore insufficient for a
positive refinement theorem.

## 4. Formal obstruction

Let `R_v1` be the exact semantic profile exposed by the current TypeScript
contracts. Let `Ready(R)` mean that a runtime projection supplies a trusted
current-head witness, a supported outcome with a responsibility owner, a
canonical Permit, an invariant witness, an exact one-target revision relation
and an atomic admission boundary.

```math
R_{v1}.\mathrm{permit}
=\mathrm{LocalEligibilityNotCanonicalPermit}
```

```math
R_{v1}.\mathrm{outcome}
=\mathrm{RepresentedNotCausalCredit}
```

The new Lean module proves:

```math
\neg\mathrm{Ready}(R_{v1})
```

and, for any canonical-learning objects,

```math
\neg\mathrm{RefinesLearn}(R_{v1},S,\tau,y,c,p,S').
```

This is not a failure of Lean or TypeScript. It is a proof that the current
engineering boundary honestly stops before canonical learning.

## 5. TypeScript fail-closed projection

The companion TypeScript module publishes a strict immutable profile using the
exact source status literals. Its canonical JSON codec preserves the same
verdict and blockers across byte round trips. Type imports tie those literals
to the existing Permit-resolution and outcome-evidence interfaces, so a source
contract rename or semantic widening causes compilation or regression failure.

The projection has no method that issues Permit, writes canonical state,
dispatches an external effect, assigns causal credit or invokes learning. Its
only positive claims are bounded structural mappings.

## 6. Exact claim ceiling

The Lean proof establishes an obstruction within the declared cross-language
model. TypeScript compilation and exact-byte tests show that the checked-in
projection uses the declared source literals. They do not constitute a
machine-checked semantics of TypeScript, prove that arbitrary JavaScript
execution refines Lean, authenticate a runtime head or outcome, or prove HSWM
efficacy.

Positive refinement remains blocked until all of the following are separately
specified and evidenced:

1. an authenticated current-head witness rather than local observation alone;
2. an exact one-target current-revision relation, or a proved multi-write
   generalization;
3. independently attributable evaluator evidence beyond declared role text;
4. an outcome receipt with exactly one responsibility owner and an explicit
   revision-support verdict;
5. a canonical Permit decision re-evaluated at the admission linearization
   point rather than a reusable local-eligibility record;
6. an executable schema-relative invariant witness; and
7. an atomic owner-valid admission transition whose result can be related to
   changed next behavior.

No scientific result, FCL law, G0/G1 gate, causal learning, cognition or
complete HSWM realization follows from this obstruction proof.

The subsequent
[`owner-bound outcome judgment boundary`](HSWM_OWNER_BOUND_OUTCOME_JUDGMENT_BOUNDARY_2026-08-31.md)
adds the missing observation-owner and revision-support-judgment shapes as a
new separately scoped contract. It does not retroactively change this exact v1
source profile and does not remove the truth, causal-credit, Permit, invariant,
current-head or admission blockers.
