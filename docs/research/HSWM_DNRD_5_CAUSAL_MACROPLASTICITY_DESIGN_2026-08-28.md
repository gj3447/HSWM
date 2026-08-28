# HSWM-DNRD-5 causal macroplasticity design

- Date: 2026-08-28
- Status: `DESIGN_NOT_PREREGISTERED / UNMEASURED / NO_SCIENTIFIC_RESULT`
- Experiment ID: `HSWM-DNRD-5`
- Decision status: no execution, source freeze, manifest, preregistration, or
  ratification is authorized by this design.

## Target identity, evidence boundary, and conceptual delta

HSWM's target is one token-native LLM-function macro-neural network.  Its
evolving hypergraph is at once its living harness, world model, and continuous
learner; these labels do not identify separable subsystems.  The relevant
closed loop is: token-native transition produces a sealed trajectory; an
independent outcome is attributed to that trajectory; credit authorizes a
provenance-bound, owner-valid canonical revision; and that revision causes
changed later traversal or transition.  Repository code, a graph/KG view,
runtime bridge, CI, manifest, marker, or judge are bounded projections and
evidence interfaces, not HSWM cognition or learning.

DNRD-1 through DNRD-3 are consumed but unjudged for their narrow routing
questions.  DNRD-4 reached a pre-marker static instrument refusal, and DNRD-4S1
is a distinct successor limited to engineering conformance.  In particular,
the DNRD-4S1 `VOID_PROTOCOL` instrument failure is neither a DNRD-5 outcome,
covariate, pilot estimate, control result, exclusion, nor effect input.  It
must not be pooled, repaired, retried, or used to set DNRD-5 thresholds,
allocation, stopping, or interpretation.

The conceptual delta is therefore scientific rather than another routing
harness: DNRD-5 asks whether independently evaluated outcomes *causally*
change a bounded canonical macro-state in a way that changes fresh subsequent
behavior, while matched credit-breaking interventions do not.  This is still
a small falsifiable projection of the constitutional target, not a claim that
the full living hypergraph, world model, or continuous learner has been built.

## Proposed schema-relative causal object

Before any implementation, the future DNRD-5 schema must name each admitted
atom version below and assign exactly one schema-relative responsibility owner.
The owner is the canonical accountability address, not a claim that one agent
performs every operation or authorizes itself.

| Canonical atom kind | Sole schema-relative owner | Required typed references and invariant |
| --- | --- | --- |
| `episode_spec` | `experiment_custodian` | `schema_ref`, block assignment, task contract, W0 reference; immutable after sealing |
| `token_trajectory` | `transition_executor` | `episode_spec_ref`, readset, token/action trace, model/runtime provenance, seal receipt; sealed before outcome access |
| `hidden_outcome` | `outcome_evaluator` | `trajectory_ref`, evaluator/version commitment, timestamp, outcome receipt; inaccessible to transition/update paths before release |
| `credit_decision` | `credit_adjudicator` | `trajectory_ref`, `hidden_outcome_ref`, assigned arm, decision time, admissible update scope; outcome binding is immutable |
| `macro_revision` | `canonical_state_custodian` | prior and successor atom versions, `credit_decision_ref`, writeset, validator and restore references; one owner for every revised atom |
| `fresh_probe` | `probe_custodian` | new task/context seed, post-revision state reference, hidden answer/evaluator reference; no training trajectory or outcome leakage |
| `analysis_record` | `independent_judge` | sealed raw references, prespecified estimand/test, missingness and terminal classification; cannot revise learning state |

`token_trajectory -> hidden_outcome -> credit_decision -> macro_revision ->
fresh_probe` is a chain of typed references, not a prose explanation.  Every
state transition must carry provenance, readset/writeset, validator reference,
scope, authorization reference, decision time, and restore path.  The schema
must require `Inv_sigma`, `Permit_sigma`, and exactly-one-owner checks before
admission.  The only intended learning path is an outcome-bound canonical
revision or transition-disposition revision; prompt replay, cache mutation,
readout editing, evaluator feedback in a probe, or a bridge-side rule change
does not count as learning.

## Feasibility design and estimand

This is a feasibility option, not a committed sample size.  It uses 64
independent latent-rule blocks, each with matched tasks and a hidden evaluator.
At most five model calls are allowed per block, for a hard maximum of 320
generation calls.  The final allocation, task generator, model/runtime
identity, block independence mechanism, and call accounting must be frozen in
a later preregistration; none is fixed here.

Within each block, the latent rule and fresh probe are held from the model and
the update path.  The proposed treatment contrasts are:

| Arm | Causal role | Required interpretation |
| --- | --- | --- |
| `ACTIVE` | outcome is sealed then validly bound to credit before the allowed canonical revision | reference outcome-to-revision path |
| `CREDIT_REVERSAL` | matched outcome sign/credit mapping is reversed before the otherwise identical revision decision | tests whether later behavior follows credit rather than incidental trajectory features |
| `OUTCOME_TIME_SHUFFLE` | outcome/credit is time-shuffled across matched blocks after trajectories are sealed | tests temporal attribution rather than aggregate outcome exposure |
| `EXACT_W0_ROLLBACK` | no learned successor persists; fresh probe uses exact pre-episode W0 | tests whether any effect requires the admitted macro-revision |

The primary block-level outcome is a predeclared binary success on the fresh
probe, scored by the independent hidden evaluator.  The proposed primary
estimand is the vector of three paired block-level mean contrasts
`ACTIVE - CREDIT_REVERSAL`, `ACTIVE - OUTCOME_TIME_SHUFFLE`, and
`ACTIVE - EXACT_W0_ROLLBACK`, together with their minimum `Delta_min`.  A
candidate joint success rule requires every contrast, and therefore
`Delta_min`, to be at least an absolute 15 percentage points; every
familywise-adjusted one-sided test must pass; and every simultaneous lower
confidence bound must exceed zero.  Merely observing an update or reproducing
a training response cannot satisfy this rule.  The 15-point floor is a
decision threshold, not proof of general HSWM utility.

The evaluator must be independently implemented or held behind an interface
that the executor, model prompt, revision path, and analyst cannot influence
after sealing.  It must receive only its permitted probe material and return a
versioned outcome receipt.  Hidden labels, reference answers, and any evaluator
diagnostic must never be injected into the model context, canonical revision,
or future probe before the relevant score is committed.

## Sealing, analysis, and error control

For every block the experiment seals, in this order: assignment commitment;
W0 identity; trajectory; hidden-outcome/evaluator commitment; credit decision;
allowed revision or exact rollback; and the fresh-probe task identity.  The
fresh probe is generated or selected independently of the training trajectory
and is evaluated only after its own response is sealed.  Its context excludes
the training answer, outcome, credit label, revision rationale, and any direct
identifier that permits recovery of them.

The independent judge receives only sealed artifacts and verifies chronology,
hashes, schema ownership, typed-reference closure, authorized writes, W0
identity, evaluator separation, randomized state-to-arm assignment, and call
accounting before analysis.  Its primary inferential procedure is an exact
paired randomization test over the complete matched block contrasts using only
the frozen within-block assignment space.  The three prespecified ACTIVE
versus-control contrasts are evaluated with a max-statistic randomization
distribution, yielding familywise-error-controlled adjusted p-values and
simultaneous lower confidence bounds.  The preregistration must state the
one-sided familywise alpha, directionality, statistic, tie rule, permutation
universe/enumeration or deterministic Monte Carlo seed, and the joint success
rule.  No unsealed adaptive analysis may substitute for this judge.

Sixty-four blocks cannot guarantee 80% power for a generic 15-point difference:
power depends on baseline success, within-block correlation, assignment,
missingness, and the three-contrast familywise correction.  A future
preregistration must publish an explicit conditional power calculation across
declared nuisance scenarios, and must call the study underpowered or
inconclusive where those assumptions do not support its stated objective.
Neither an observed 15-point difference nor a non-significant test alone
establishes absence of macroplasticity.

## Integrity, terminals, and nonclaims

Each block is complete only if all assigned arms, seals, evaluator receipts,
fresh probes, and exact W0 verifications pass their prespecified checks.
Missingness is never silently imputed or selectively dropped: the preregistration
must retain raw reason codes, report arm/block counts, and specify whether any
affected block produces `VOID_PROTOCOL`, `INCONCLUSIVE_OCCURRENCE`, or a
conservative no-go analysis.  After the first semantic marker, there is no
resume, duplicate execution, substituted model call, reindex, or second pulse.

The following are validity failures, not favorable or unfavorable efficacy
data: outcome leakage into trajectory/revision/probe; evaluator access or
feedback contamination; source/runtime/schema identity drift; noncanonical or
multi-owner writes; missing provenance; mutation after a seal; unaccounted
calls; unstable W0 rollback; duplicate block/seed; or invalid randomization.
The frozen protocol must define which conditions make the entire occurrence
`VOID_PROTOCOL` and which make it a sealed `INCONCLUSIVE_OCCURRENCE`.  Stability
checks must show that exact W0 restoration, same sealed inputs, and the allowed
deterministic components reproduce their declared state/readout constraints;
they are integrity instruments, not causal effects.

Even a complete statistically positive result would support only this bounded
causal macroplasticity claim: under the frozen task/schema/runtime and hidden
evaluator, outcome-bound canonical revision changed later fresh-probe behavior
relative to the declared matched controls.  It would not establish general
intelligence, robust utility, independent human benefit, consciousness,
world-model adequacy, topology morphogenesis, long-horizon continual learning,
population generalization, or that any repository harness/KG/MCP is HSWM.

## Required end-to-end contract vector

The prior diagnostic gap showed that a producer can serialize an apparently
valid artifact under an ordering semantics rejected later by executor and
judge.  DNRD-5 may not rely on pairwise unit tests for this boundary.  Before
preregistration it must define one versioned end-to-end contract vector that is
consumed unchanged by registration, executor, evaluator gateway, and judge.
The vector must include valid and adversarial cases for: canonical serialized
ordering; every atom's sole owner; typed-reference closure; provenance/hash
binding; assignment and seal chronology; permitted versus forbidden outcome
access; W0 rollback identity; fresh-probe isolation; arm mapping; exact
randomization inputs; missingness terminals; and generation-call accounting.

For each vector case, the frozen expectation is either a fully accepted
occurrence configuration or a specific pre-marker refusal/terminal.  The
production producer and independent judge remain separate implementations;
both must consume the same frozen byte-level vector and agree on every valid
and adversarial case without importing each other's production derivation.
Source-freeze CI must additionally pass at least one complete production-shape
`register -> execute -> evaluator -> judge` acceptance path, not only mocks or
early expected refusals.  This prevents an implementation-only green test
suite from being mistaken for scientific readiness.

## Next boundary

This document is a design hypothesis.  Its next legitimate step is a separate
scientific-boundary review that may alter the design, followed—only if accepted—
by a new implementation, source freeze, preregistration, and future occurrence.
Until then it contributes no measured result, no ratification request, and no
authorization to run model calls.

The target-identity constraints are from
`docs/canon/HSWM_CONSTITUTION_2026-08-20.md`; the immediate DNRD-4S1 evidence
boundary is `docs/research/HSWM_DNRD_4S1_SUCCESSOR_SCIENTIFIC_BOUNDARY_2026-08-28.md`.
