# HSWM atomic admission does not entail behavioral or causal efficacy

> **Status:** `SECONDARY_AI_FORMAL_COUNTERMODEL / EFFICACY_NOT_ENTAILED / SCIENTIFIC_UNJUDGED`
>
> **Target authority:**
> [`HSWM Constitution`](../canon/HSWM_CONSTITUTION_2026-08-20.md)
> and the `outcome -> credit -> revision -> fresh behavior` target invariant in
> the
> [`adaptive research strategy`](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)
>
> **Predecessor formal boundary:**
> [`head-bound Permit, invariant and atomic admission`](HSWM_ATOMIC_PERMIT_INVARIANT_ADMISSION_LEAN_2026-08-31.md)
>
> **Formal artifact:**
> [`HSWMAtomicAdmissionNonEntailment.lean`](../../formal/HSWMAtomicAdmissionNonEntailment.lean)

## 1. Canonical role

HSWM's target is one outcome-bound continuous learner, not a state ledger that
merely accepts well-typed revisions. Atomic admission is one transition inside
the evolving schema-relative hypergraph. Behavioral readout, external outcome
truth and causal attribution are meanings of that same HSWM process, but they
are not logically created by a successful admission receipt.

The canonical target loop remains:

```text
sealed trajectory
  -> independently attributable outcome
  -> causal support judgment
  -> owner/Permit/Inv-valid atomic revision
  -> fresh behavior under a declared probe semantics
  -> intervention/control evidence
```

The preceding formal work reaches a specification of the fourth item. It does
not skip to the fifth or sixth.

## 2. Target identity versus current proof

The target requires evidence that the admitted state changes behavior in the
declared direction and that the change survives the appropriate sham,
rollback, delayed-credit and negative controls. Current Lean proofs establish
typed bindings, necessary conditions, frame properties, successor uniqueness
and one finite consistency witness.

Those results deliberately leave four interpretations as parameters:

| Interpretation | Question outside structural admission |
| --- | --- |
| behavior semantics | what response does a state produce for a fresh probe? |
| external outcome truth | does the judgment evidence correspond to the world? |
| principal authentication | do declared principal values identify authenticated independent actors? |
| head trust | is the supplied head current under the required anti-rollback/trust model? |

No field-name equality can derive these interpretations.

## 3. Conceptual delta: an explicit non-entailment test

Let `B(S,q)` be a declared behavior for state `S` and fresh probe `q`.
Behavioral change means:

```math
\mathrm{BehaviorChanged}(B,S,S')
\;:=\;
\exists q,\;B(S,q)\neq B(S',q).
```

If `AtomicLearnAdmission(S,S')` alone entailed behavioral efficacy, every
admissible behavior interpretation would need to distinguish `S` and `S'`.
But a constant interpretation is a valid model of the current formal
signature and yields no distinguishing probe. The already constructed atomic
admission still exists in that model.

Likewise, the current signature permits an interpretation in which every
declared evidence digest is externally false, no symbolic principal is
authenticated, and no symbolic head is trusted. The admission relation does
not inspect any of those predicates, so its witness remains intact.

These are countermodels to implication, not claims that the real outcome is
false, that real principals cannot be authenticated, or that a trusted head is
impossible.

## 4. Machine-checked boundary

The Lean module imports the finite atomic-admission witness and proves:

- the exact admitted predecessor and successor have no behavioral difference
  under a constant behavior semantics;
- therefore one `AtomicLearnAdmission` witness coexists with the negation of
  `BehaviorChanged`;
- the support judgment can coexist with a deliberately false external-truth
  interpretation;
- the admission witness can coexist with unauthenticated actor, authorizer,
  evaluator and adjudicator interpretations;
- the admission witness can coexist with an untrusted-head interpretation;
  and
- a conjunction named `IntegratedEfficacyBridge` requires all of behavioral
  change, external truth, role authentication and predecessor-head trust, and
  is false in the countermodel despite atomic admission.

This establishes that no theorem from the current structural premises may
conclude the integrated efficacy bridge without adding and discharging new
premises.

## 5. Research consequence

The next positive scientific bridge cannot be another status rename or schema
field. It must declare a behavior semantics and fresh probe domain, bind the
exact admitted revision to intervention and control arms, obtain independently
attributable outcomes, and evaluate a frozen success criterion. A valid null
result retires or reroutes that exact mechanism family; it cannot be relabeled
as structural success or rescued by downstream scale.

## 6. Exact claim ceiling

The countermodel proves non-entailment inside the formal signature. It does not
show that HSWM cannot learn, that the concrete consistency witness is a real
HSWM execution, or that any checked-in scientific experiment passed or failed.
It neither shrinks the USER_PRIMARY target nor changes any FCL criterion.

No runtime mutation, causal-credit assignment, G0/G1 judgment, research
receipt or scientific result is created by this phase.
