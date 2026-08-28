# HSWM-DNRD-5 scientific-boundary review

- Date: 2026-08-28
- Status: `DESIGN_DECISION_ONLY / NOT_PREREGISTERED / UNMEASURED / NO_SCIENTIFIC_RESULT`
- Scope: review of the initial DNRD-5 design at commit
  `0669ab891eb53def0c3dfe82b340e7afc47aded4`; this is not an experiment
  preregistration, source freeze, authorization to execute, or evidence claim.

## Decision

The target identity is accepted: HSWM is one token-native LLM-function
macro-neural network whose canonical, evolving hypergraph jointly plays the
living-harness, world-model, and continuous-learning roles.  A bounded test
must therefore distinguish a provenance-bound, owner-valid, outcome-authorized
canonical revision from prompt replay, cache mutation, bridge-side rules, or
readout editing.  This is a direct application of the closed loop in
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md),
not evidence that the full target has been built.

The initial design is **not preregistration-ready**.  In particular, its
`64`-block / `320`-call arrangement is rejected as confirmatory: it did not
define a coherent experimental unit, clone/arm allocation, call accounting, or
randomization universe compatible with three paired contrasts.  Its
`CREDIT_REVERSAL` and cross-block `OUTCOME_TIME_SHUFFLE` controls are also
rejected.  Reversal can measure correct versus corrupted supervision; a
cross-block outcome can be semantically invalid for the receiving latent rule.
Neither isolates the causal effect claimed for outcome-bound credit.

The following is frozen as a **design decision** for the next scientific
boundary.  It may be changed only by a later, explicit boundary review; it is
not yet an experiment commitment.

## Corrected occurrence shape

The proposed occurrence has **300 independent block-clusters**.  A block is
the sole statistical unit: its four arm branches, probe variants, evaluator
subitems, retries, and traces never add observations.  A later preregistration
must freeze the latent-rule generator, the criterion for independence between
blocks, and the block seed schedule.

Each block has four opaque, independently addressed canonical fork lineages
from one sealed `W0`.  They are byte-identical in their behaviorally readable
canonical state at fork time and are randomly permuted to arm labels after the
clone identities are sealed.  The model, evaluator, and probe prompt receive
neither arm labels nor clone identifiers.  All inference is therefore based on
`N = 300` complete block-clusters, not nominally independent model calls.

At most **nine generation calls** are allowed per block, hence at most
**2,700 generation calls** in an occurrence:

1. One pre-outcome training/trajectory call from sealed `W0`.
2. One `ACTIVE` post-trajectory revision/proposal call with genuine sealed
   evaluator feedback and a valid credit capability.
3. One `OUTCOME_INDEPENDENT_SHAM` post-trajectory revision/proposal call with
   a precommitted placebo receipt independent of the trajectory's true outcome.
4. One `DELAYED_NO_CREDIT` post-trajectory call in which the true outcome is
   withheld; it has no admission capability and no learned successor.
5. One `EXACT_W0_ROLLBACK` post-trajectory revision/proposal call with the
   same genuine feedback and valid credit capability as `ACTIVE`.
6. Four fresh-probe calls, one for each arm, each in a new isolated model
   session and in randomized opaque order.

The state action is fixed as follows.

| Arm | State before its fresh probe | Causal purpose |
| --- | --- | --- |
| `ACTIVE` | The canonical successor admitted from its genuinely outcome-bound, permitted revision | Reference outcome-to-revision path |
| `OUTCOME_INDEPENDENT_SHAM` | A schema-valid placebo successor whose actual admitted target set, atom/incidence shape, writeset cardinality, envelope class, projection budget, and validation terminal match active; its precommitted receipt is independent of the realized local outcome and distribution-matched conditional on public task strata, while carrying no hidden key/reference answer, probe material, or genuine outcome | Separates an outcome-bound revision from a matched generic model/state rewrite |
| `DELAYED_NO_CREDIT` | Exact behavioral `W0`; the genuine outcome remains escrowed until every probe response is sealed, and no revision is admitted | Separates outcome availability before behavior from later audit disclosure |
| `EXACT_W0_ROLLBACK` | The active-style successor is admitted in a sealed staging branch and then restored to exact behavioral `W0` before the probe | Tests whether persistence of the admitted canonical successor is necessary |

The rollback branch may retain immutable occurrence receipts only outside its
permitted probe readset.  Its declared behavioral root and readset projection
must hash-identically equal `W0`; otherwise the whole occurrence is invalid.
The delayed outcome may be released only after all response seals and may not
cause any transition in this occurrence.

The placebo contract may not borrow a donor outcome from another confirmatory
block, because that would add cross-block dependence.  If the genuine
outcome's conditional receipt distribution cannot be frozen and matched before
source freeze, the primary contrast must be downgraded to true versus synthetic
feedback in a new boundary review rather than advertised as isolated
outcome-binding credit.

## Information flow and causal question

For block `b`, let `T_b` be the sealed pre-outcome trajectory, `Y_b` the
independent evaluator outcome, `G_b` the randomized mapping from opaque clone
IDs to arms, `M_b(a)` the behaviorally readable canonical state before the
probe under arm `a`, `Q_b(a)` the sealed fresh-probe response, and
`Z_b(a) in {0,1}` its hidden-evaluator score.  The intended causal path is:

```text
latent block / W0 / held-out probe -> T
T -> independent outcome Y
G -> arm-specific credit and admitted state M
Y -> valid ACTIVE or ROLLBACK credit -> M -> Q -> Z
```

The treatment exclusion condition is strict: arm, outcome, evaluator
diagnostics, raw trajectory, candidate proposal, audit receipt, cache,
filesystem, network, session history, and another clone's state have no route
to a fresh-probe model call except its declared, byte-hashed canonical readset
projection.  The fresh probe identity and hidden answer are committed before
the trajectory outcome is released; the response is sealed before scoring.

The primary finite-block estimand is

```math
tau_AS = (1/300) sum_b [ Z_b(ACTIVE) - Z_b(OUTCOME_INDEPENDENT_SHAM) ].
```

The secondary mechanism estimands are `tau_AD` for `ACTIVE -
DELAYED_NO_CREDIT` and `tau_AR` for `ACTIVE - EXACT_W0_ROLLBACK`.  The later
preregistration must use three one-sided exact conditional paired tests over
the frozen within-block ACTIVE/control label swaps, Bonferroni adjustment at a
familywise alpha of `.05`, and matching asymptotic paired-block simultaneous
lower confidence bounds.  The exact p-values address pairwise sharp nulls;
the lower bounds address average block effects and must not be described as
exact randomization intervals.  An equicorrelated max-statistic calculation is
sensitivity analysis only.  The bounded positive claim requires the primary
contrast and both secondary contrasts to pass their prespecified joint rule.
The exact label additionally requires a pre-marker, disjoint production-shape
qualification showing that identical request/runtime/RNG bytes reproduce
identical outputs; a seed alone does not establish that property.  The exact
p-values reject sharp-null hypotheses, while the separately labeled asymptotic
lower bounds provide average-effect directional evidence.

The planning alternative is a positive `.15` average difference in each of
the three contrasts.  It is not an observed point-estimate floor or a claim
that the true effect is at least 15 percentage points.  At `q=.50` and
`delta=.15`, the assumed iid block-level marginal law is `P(D=+1)=13/40`,
`P(D=-1)=7/40`, and `P(D=0)=20/40`.  At `n=300`, its exact finite-`n` marginal
success probability for one contrast is `p_single ~= .9354136401`.  With no
assumption about dependence among the three contrast-success events, the
all-three Fréchet lower bound, obtained by a union bound on failures, is
`max(0, 3 p_single - 2) ~= .8062409204`.  It is below `.8` at `n=297`, and
`n=298` is the first integer at or above `.8`; 300 is a fixed small margin, not
an independence claim.  Normal and correlation-based calculations are
sensitivity analyses only: a `rho=0` calculation is not claimed conservative.
The full nuisance-scenario grid and no-absence interpretation remain mandatory.

This inference requires, and must actively test where possible: consistency;
exchangeability of the four pre-arm clone lineages; no cross-clone or
cross-session interference; valid, arm-blind outcome and probe evaluation;
probe independence from trajectory and revision content; correct treatment
adherence; exact W0 restoration; and independently generated block-clusters.
These are assumptions and integrity conditions, not findings supplied by the
eventual p-values.

## Canonical and permission prerequisites

The future schema must give each admitted atom version exactly one
schema-relative responsibility owner.  It must additionally represent, with
typed references and independent owners where they persist or have effect:
assignment commitment, clone/fork incidence, `W0` snapshot, evaluator/version
commitment, placebo commitment, outcome-credit escrow, outcome escrow/release
capability, placebo receipt, candidate
validation, trajectory contract, seal receipt, arm mapping, probe commitment,
projection policy and state/readset projection, permit policy, current
authorization decision, capability issuance/release, revocation status,
transition/admission receipt, grant snapshot, and rollback transaction.

For every revision or restore transition, the receipt must bind its trajectory,
outcome or placebo source, exact readset and writeset, scope, validator,
decision time, authorization, and pre-existing restore policy/capability.
`Permit_sigma(S,e)` must be
checked at that time using a current, separately owned authorizer/grant record
scoped to the exact effect.  A state owner, transition executor, or credit
adjudicator cannot self-authorize by being named as an owner.  For every
state-changing scope, the authorizer principal must be unequal to the actor,
state/restore custodian, credit adjudicator, and authorization-record custodian;
role labels alone do not satisfy this invariant.  A DNRD-5-specific
fail-closed transaction gate must resolve those current records immediately
before CAS/journal submit and bind the resolution to transition provenance;
generic canonical-V2 authorization fields do not supply that capability.

## Required preregistration gates

No DNRD-5 source freeze or occurrence may proceed until a separate
preregistration freezes all of the following.

- The schema, owner map, typed-reference closure, `Inv_sigma` and
  `Permit_sigma` checks, capability lifecycle, and exact behavioral-readset
  definition.
- The task/probe/evaluator generators, versions and hidden-key commitments;
  block independence definition; `W0` fork identity; seed derivation; and
  complete arm assignment/permutation universe.
- The exact nine-call ledger, fresh-worker/session isolation, denied
  network/undeclared-file access, model/runtime identity, and prohibition on
  hidden caches or cross-arm state.
- Byte-level sealing chronology; evaluation blindness to arm, clone ID and
  order; placebo-receipt distribution matching and independence proof; and the
  rule that hidden task keys/reference answers, probe material, and genuine
  outcome content cannot enter sham state.
- The primary and secondary estimands, alpha, `.15` planning alternative,
  exact conditional statistic, Bonferroni rule, asymptotic confidence
  construction, conditional-power scenario grid, and missingness rule.
- An end-to-end contract vector consumed independently by registration,
  executor, evaluator gateway, and judge, including adversarial tests that
  swap state/readsets and opaque arm labels, revoke outcome capabilities,
  attempt probe/outcome leakage, perturb rollback, and attempt cache/session
  interference.  A disjoint production-shape qualification must establish
  identical-request/runtime/RNG output reproducibility before any finite-sample
  exact-test claim is frozen.
- Terminal classification: any post-marker identity drift, unaccounted call,
  outcome/probe leak, unauthorized or noncanonical write, invalid randomization,
  nonexact rollback, or cross-arm interference is `VOID_PROTOCOL`; validly
  sealed operational missingness is occurrence-level
  `INCONCLUSIVE_OCCURRENCE`/conservative no-go, never complete-case analysis
  or a rerun.

## Commitment and authority boundary

No manual user hash echo is a gate for this program.  The operational
authorization path is a public Source-A and CI commitment, followed by a
preregistration Source-B and CI commitment, then future public randomness
before observation.  Those commitments make the planned occurrence auditable;
they are not scientific evidence and do not fabricate a user signature,
ratification, or result.

## Remaining limits

This correction remedies the original call-accounting and invalid-control
problems, but it remains a deliberately narrow projection.  It can support at
most a task- and runtime-bound causal macroplasticity result: genuinely
evaluated feedback caused an owner-valid canonical revision that changed a
fresh behavior relative to the declared controls.  It cannot establish general
intelligence, a full living hypergraph/world model, robust utility,
long-horizon learning, or human benefit.

It also leaves a substantive falsification pressure: a sufficiently capable
but non-HSWM-like fixed procedure could mimic this small loop.  The
information-flow, state-swap, arm-label, cache, and rollback adversarial tests
can rule out undeclared routes in this occurrence, but not prove a unique
ontology from behavioral data.  A successful result therefore remains bounded
evidence for the declared causal mechanism, not proof of the constitutional
target.
