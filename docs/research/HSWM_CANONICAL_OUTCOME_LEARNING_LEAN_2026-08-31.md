# HSWM canonical outcome-learning Lean boundary

> **Status:** `SECONDARY_AI_FORMAL_PROTECTIVE_BELT / SCIENTIFIC_UNJUDGED`
>
> **Target authority:**
> [`HSWM Constitution`](../canon/HSWM_CONSTITUTION_2026-08-20.md),
> [`schema-relative single-owner philosophy`](HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_SCIENTIFIC_PHILOSOPHY_2026-08-26.md),
> and the
> [`adaptive research strategy`](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)
>
> **Formal artifact:**
> [`formal/HSWMCanonicalLearning.lean`](../../formal/HSWMCanonicalLearning.lean)

## 1. Why this proof comes before another runtime slice

The next empirical boundary requires an independently owned outcome and
evaluation path. Implementing an evaluator first would leave the central
question implicit: which facts must be present before an outcome may authorize
a durable canonical revision? This document fixes that question before any new
TypeScript or Python runtime mechanism is added.

The target identity is unchanged. HSWM remains one token-native,
LLM-function macro-neural process whose canonical relational state acts as
living harness, world model, and continuous learner. This proof does not create
another subsystem. It specifies a necessary admission relation over the same
schema-relative canonical state.

## 2. Conceptual delta

The older Lean cellular modules establish bounded laws about typed cell
composition, routing, replay, and durable outbox states. They do not formalize
the current canonical atom language introduced after the fixed `H/W/A/F/Pi`
decomposition was retired.

The new formal boundary uses no fixed component partition. Its primitive state
is a partial map from a fork-safe atom address
`(schema_version, lineage_id, atom_uid)` to one current immutable atom version.
Every current version carries exactly one schema-relative responsibility owner.
Historical versions are retained separately rather than overwritten.

The learning relation binds five typed objects:

1. a trajectory sealed before the outcome;
2. an outcome receipt with one responsibility owner and one evaluator;
3. a revision proposal against one exact current revision;
4. a current authorization decision with target, trace, scope, and
   authorization-reference bindings; and
5. a schema-relative invariant supplied independently of the proposal.

Owner, actor, proposer, evaluator, outcome owner, and authorizer are distinct
roles. The same principal may occupy more than one role when a schema permits
it, but no role predicate derives another. In particular, owner identity cannot
turn a denied authorization into a permit.

## 3. Formal admission contract

Let `S` be the current canonical state, `tau` a pre-outcome sealed trajectory,
`y` an outcome receipt, `c` a revision proposal, `p` a current permit decision,
and `Inv` the schema-relative invariant. The Lean relation admits only the
following form:

```math
\mathrm{Learn}_{\sigma}(S,\tau,y,c,p,S')
\Rightarrow
\begin{aligned}
&\mathrm{current}_{S}(c.\mathrm{target})=a,\\
&c.\mathrm{expectedRevision}=a.\mathrm{revision},\\
&c.\mathrm{trace}=y.\mathrm{trace}=p.\mathrm{trace}=\tau.\mathrm{trace},\\
&\mathrm{sealedBeforeOutcome}(\tau),\\
&\mathrm{independentEvaluator}(y,\tau,c),\\
&\mathrm{independentOutcomeOwner}(y,\tau,c),\\
&y.\mathrm{verdict}=\mathrm{supports},\\
&\mathrm{Permit}_{\sigma}(p,c),\\
&\mathrm{Inv}_{\sigma}(S,c),\\
&S'=\mathrm{revise}(S,a,c).
\end{aligned}
```

`revise` changes only the addressed current atom, preserves that atom's
responsibility owner, records the sealed trace as provenance, and prepends the
previous version to history. Ordinary learning therefore cannot smuggle an
owner migration into a payload revision.

## 4. Machine-checked obligations

The Lean module proves the following bounded obligations:

- every present current atom has a unique responsibility owner;
- every outcome receipt has one responsibility owner by construction;
- every admitted learning transition requires trace, evaluator, outcome-owner,
  supported-outcome, current-revision, invariant, and Permit conditions;
- self-evaluation, actor-owned outcome, proposer-owned outcome, unsealed trace,
  trace mismatch, missing current atom, stale or reused revision, unsupported
  outcome, mismatched Permit binding, denied or inactive Permit, or failed
  invariant makes the learning relation uninhabited;
- even when the atom owner and authorizer are the same principal, an explicit
  denial cannot be overridden;
- an admitted revision preserves the target owner, changes no other current
  atom, and archives the prior version.

These are necessary-condition and frame theorems. They are intended to become
the specification side of a later TypeScript/Effect refinement boundary.

## 5. Exact claim ceiling

Lean proves the consequences of the declared model; it does not prove that a
real evaluator is independent, an outcome is true, a digest is collision-free,
an authorizer is legitimate, or a TypeScript implementation conforms to this
model. It also does not establish causal credit, useful learning, changed next
behavior, G0/G1, any FCL law, cognition, consciousness, personhood, or complete
HSWM realization.

No runtime mechanism is promoted by this artifact. A future implementation must
first define a byte-level refinement map from its state, receipts, and errors to
these Lean objects and demonstrate conformance without weakening any guard.
