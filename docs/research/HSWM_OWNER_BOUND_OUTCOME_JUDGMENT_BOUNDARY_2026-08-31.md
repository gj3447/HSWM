# HSWM owner-bound outcome judgment boundary

> **Status:** `SECONDARY_AI_FORMAL_TYPED_CONTRACT / REPRESENTED_NOT_TRUTH_NOT_CAUSAL_CREDIT / SCIENTIFIC_UNJUDGED`
>
> **Target authority:**
> [`HSWM Constitution`](../canon/HSWM_CONSTITUTION_2026-08-20.md),
> [`schema-relative single-owner philosophy`](HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_SCIENTIFIC_PHILOSOPHY_2026-08-26.md),
> and the owner/type separation in the
> [`DNRD-5 causal macroplasticity design`](HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md)
>
> **Formal artifact:**
> [`HSWMOutcomeJudgment.lean`](../../formal/HSWMOutcomeJudgment.lean)
>
> **TypeScript artifact:**
> [`canonical-atom-v2-outcome-judgment.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-outcome-judgment.ts)

## 1. Canonical role

HSWM remains one token-native LLM-function macro-neural process. Outcome
observation and revision-support judgment are typed atoms inside its one
schema-relative evolving hypergraph. They are not an external learning engine
or two new cognitive subsystems.

The continuous-learning loop requires an independently attributable outcome
before causal credit and canonical revision. An observation record alone does
not answer whether a particular revision proposal is supported. Conversely, a
support label without an exact observation, trace and proposal binding is a
self-authored assertion rather than an outcome-bound judgment.

## 2. Conceptual correction

The first canonical-learning Lean boundary intentionally compressed the
downstream evidence into one `OutcomeReceipt`. That was sufficient to prove
necessary admission guards, but it is not the final canonical atomization.

This phase separates two lifecycle and correction responsibilities:

| Atom | Exactly one responsibility owner | Meaning | Forbidden inference |
| --- | --- | --- | --- |
| outcome observation | outcome-evidence owner | an evaluator attributes one observed/failed/unknown result to a sealed trace | observation implies proposal support, truth or causal credit |
| revision-support judgment | credit-decision owner | an adjudicator applies one criterion to an exact observation and exact proposal revision | support label implies truth, Permit, invariant satisfaction, admission or learning |

The owners, evaluator and adjudicator are predicates with separate obligations.
Principal equality never derives permission. For this bounded boundary, the
observation owner and judgment owner must differ, the evaluator and adjudicator
must differ, and each must differ from the trajectory actor and revision
proposer. These are address-level separation conditions, not authentication or
proof of real organizational independence.

## 3. Typed binding

Let `tau` be a sealed trajectory, `o` an outcome observation, `c` a revision
proposal, and `j` a revision-support judgment. A support witness requires:

```math
\begin{aligned}
&o.\mathrm{trace}=j.\mathrm{trace}=c.\mathrm{trace}=\tau.\mathrm{trace},\\
&j.\mathrm{observation}=o.\mathrm{id},\\
&j.\mathrm{target}=c.\mathrm{target},\\
&j.\mathrm{expectedRevision}=c.\mathrm{expectedRevision},\\
&j.\mathrm{candidateRevision}=c.\mathrm{candidateRevision},\\
&j.\mathrm{verdict}=\mathrm{supports},\\
&\mathrm{SeparatedRoles}(\tau,o,c,j).
\end{aligned}
```

An outcome-evidence package contains one observation and an optional judgment.
The Lean relation has no constructor when the judgment is absent, rejects or
is indeterminate, binds another trace or revision, or collapses the required
role addresses.

The explicit judgment can then be projected into the earlier abstract
`OutcomeReceipt` used by `Learn`. This projection does not admit anything: a
separate Lean `Learn` witness must still provide the current revision, canonical
Permit, schema invariant and state-frame conditions.

## 4. Machine-checked obligations

The Lean module proves:

- observation and judgment records each have one responsibility owner by
  construction;
- any outcome-evidence learning witness contains an explicit support judgment
  bound to the exact observation, trace, target and two revision identifiers;
- observation without judgment cannot learn;
- a rejecting or indeterminate judgment cannot learn;
- actor/proposer ownership or evaluation/adjudication collapse cannot learn;
- a valid support judgment projects the exact trace, support verdict,
  responsibility owner and adjudicator required by the abstract Lean outcome;
  and
- even a well-formed judgment does not remove the independent requirement for
  the underlying `Learn` transition.

## 5. TypeScript boundary

The companion TypeScript contract represents the two record kinds and one
cross-bound bundle with strict Effect schemas and exact canonical JSON bytes.
It recomputes record and proposal descriptors, checks trace/observation/
revision bindings, enforces structural chronology and the bounded role-address
separations, and returns immutable snapshots.

All positive-looking literals remain explicitly bounded:

```text
REPRESENTED_OBSERVATION_NOT_TRUTH_NOT_REVISION_SUPPORT
REPRESENTED_REVISION_SUPPORT_JUDGMENT_NOT_TRUTH_NOT_CAUSAL_CREDIT
```

The package root exports validators and byte decoders only. It exports no
evaluator, adjudicator, owner authenticator, criterion executor, Permit issuer,
admission port or learning function.

## 6. Exact claim ceiling

The formal model proves consequences of declared typed bindings. The
TypeScript implementation can prove structural and byte equality relative to
its inputs. Neither proves that an observation is true, that criterion bytes
are scientifically valid, that the criterion was actually executed, that role
addresses identify independent parties, or that an owner is authenticated.
The represented criterion timestamp is not an independently witnessed
publication time. The existing TypeScript proposal also has one `actorClaim`
and no separate proposer principal, so its bounded role check cannot discharge
the Lean model's actor/proposer distinction.

This boundary does not establish causal credit, canonical Permit, `Inv`,
admission, changed next behavior, G0/G1, any FCL law, cognition or complete HSWM
realization. It closes a representation and non-collapse prerequisite only.
