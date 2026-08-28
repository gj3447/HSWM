# HSWM-DNRD-5 causal macroplasticity design, revision 2

- Date: 2026-08-28
- Revision: `R2_AFTER_ADVERSARIAL_BOUNDARY_AND_POWER_REVIEW`
- Status: `DESIGN_REVIEWED / NOT_PREREGISTERED / UNMEASURED / NO_SCIENTIFIC_RESULT`
- Experiment ID: `HSWM-DNRD-5`
- Supersedes: the initial design at commit
  `0669ab891eb53def0c3dfe82b340e7afc47aded4`, file SHA-256
  `79ca168cdacae63e0b0038a66bf6e3c8f69fe2ca3be8fd32eca396d6c1f7271f`
- Review decision:
  [`HSWM_DNRD_5_SCIENTIFIC_BOUNDARY_REVIEW_2026-08-28.md`](HSWM_DNRD_5_SCIENTIFIC_BOUNDARY_REVIEW_2026-08-28.md)

This document fixes the accepted design direction.  It is not a source freeze,
preregistration, execution configuration, result, or permission to skip the
remaining readiness gates.

## Target identity, present evidence, and conceptual delta

HSWM's target is one token-native LLM-function macro-neural network.  Its
evolving canonical hypergraph jointly plays the roles of living harness, world
model, and continuous learner; these are views of one system rather than
separate components.  The target learning loop is:

```text
token-native transition -> sealed trajectory -> independently attributable outcome
-> causal credit under a current Permit -> owner-valid canonical revision
-> changed fresh traversal or transition
```

Repository code, a KG or ontology projection, a runtime bridge, an MCP, a
prompt, a cache, CI, and a judge are bounded interfaces or evidence instruments.
They are not HSWM cognition or learning by themselves.  The schema-relative
single-owner, typed-reference, provenance, `Inv_sigma`, and `Permit_sigma`
obligations follow
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).

DNRD-1 through DNRD-4S1 produced no verified scientific effect.  Their
consumed occurrences and instrument failures are not pilots, covariates,
exclusions, thresholds, or power inputs for DNRD-5.  In particular, no
DNRD-4S1 route value is available for reinterpretation.

The DNRD-5 conceptual delta is scientific: an independent outcome is disclosed
only after a model trajectory is sealed; a later LLM call proposes a bounded
canonical revision from that trajectory and feedback; a current capability
authorizes admission; and the resulting state must cause changed behavior on a
fresh, precommitted hidden probe.  Outcome-independent sham feedback, delayed
credit, and exact restoration provide distinct causal controls.  Merely adding
more routing, manifests, ledgers, or tests cannot satisfy this question.

## Bounded claim and hard nonclaims

The strongest possible positive result is:

> Under the frozen task generator, schema, model/runtime, evaluator, and
> assignment mechanism, genuinely attributable feedback caused an
> LLM-proposed, permitted canonical macro-disposition revision that changed
> hidden-evaluator success on fresh probes relative to outcome-independent
> sham feedback, delayed credit, and exact pre-probe restoration.

The experiment does not test foundation-model weight learning.  It tests a
bounded macro-learning transition in the one HSWM state model.  Even a positive
result cannot establish general intelligence, full world-model adequacy,
topology morphogenesis, long-horizon continual learning, practical utility,
human benefit, consciousness, or the uniqueness of the HSWM ontology.  A
fixed algorithm may be behaviorally equivalent on this finite task family;
the claim is about the declared causal mechanism, not a metaphysical identity.

## Experimental unit, allocation, and call budget

The confirmatory design uses **300 independently generated block-clusters**.
The block is the statistical unit.  Four clone branches, four probe responses,
evaluator subitems, token rows, retries, or replay checks never increase `N`.

For each block `b`, the generator commits a training task `X_b`, hidden task
state `K_b`, fresh probe `P_b`, hidden probe answer, an outcome-independent
placebo-feedback receipt, and one sealed `W0_b`.  Four opaque fork lineages are
created from `W0_b`.  Their behaviorally readable canonical roots and compiled
readsets must be byte-identical before treatment.  After all clone identities
are sealed, a future-randomness-derived uniform permutation assigns exactly
one clone to each arm.  Arm labels and clone identifiers are absent from all
model and evaluator inputs.

A complete block uses exactly nine generation calls; no retry, replacement,
resume, cache substitution, or uncounted generation is allowed.  The maximum
complete-occurrence budget is therefore **2,700 generation calls**:

| Call class | Count per block | Frozen role |
| --- | ---: | --- |
| Pre-outcome trajectory | 1 | Produce and seal the training token/action trajectory before evaluator access |
| Arm-specific revision proposal | 4 | One fresh isolated call for each opaque clone under its assigned feedback capability |
| Fresh probe | 4 | One fresh isolated call from each post-arm canonical readset, in randomized opaque order |

The revision-proposal calls and probe calls use precommitted per-clone RNG
receipts assigned before arm labels.  Decoding, RNG, request bytes, runtime,
and worker/session isolation must be reproducible enough that treatment
assignment is the only randomization used by an exact conditional test.  If
that condition cannot be demonstrated before source freeze, the preregistration
must downgrade the test from finite-sample exact to its justified
exchangeability/asymptotic status; it may not keep the stronger wording.

## Four interventions

The first model call is shared across the four fork lineages.  It sees only
`W0_b`'s permitted projection and `X_b`; it cannot see the probe, hidden task
state, evaluator, outcome, placebo receipt, arm assignment, or clone IDs.  Its
response and action form the sealed trajectory `T_b`.  A separately implemented
evaluator then returns a minimal outcome receipt `Y_b` attributable to `T_b`.

Four post-trajectory proposal calls run in fresh isolated sessions and opaque
randomized order.  Each proposal must be emitted in the frozen typed response
schema by the model; the bridge may validate, admit, reject, quarantine, or
restore it, but may not synthesize its semantic revision content.

| Arm | Proposal input and state before probe | Causal role |
| --- | --- | --- |
| `ACTIVE` | Receives the genuine `Y_b` projection under a live credit capability.  A schema-valid model proposal is validated and admitted as the canonical successor. | Reference outcome-to-proposal-to-state path |
| `OUTCOME_INDEPENDENT_SHAM` | Receives a precommitted placebo receipt independent of `Y_b`, in the same public receipt schema and canonical envelope-size class.  Its schema-valid model proposal is admitted under an independently scoped placebo capability. | Separates true outcome binding from a generic model call and state rewrite |
| `DELAYED_NO_CREDIT` | Receives a canonical `CREDIT_ESCROWED` projection, not `Y_b`.  Its output is sealed in quarantine, has no admission capability, and cannot enter the behavioral readset.  `Y_b` remains escrowed until every probe response is sealed. | Tests behavior before attributable credit is available |
| `EXACT_W0_ROLLBACK` | Receives genuine `Y_b`, produces and admits an active-style successor in a staging branch, then executes an authorized restore before the probe.  Its behavioral root and compiled readset must equal `W0_b` byte for byte. | Tests mediation by the persistent admitted successor |

The sham successor is allowed to affect behavior; otherwise `ACTIVE - SHAM`
would merely compare semantic state with an inert padding record.  Its feedback
is independent of the true outcome, while its atom kinds, declared writeset,
validation path, timing class, and canonical envelope budget are matched.  It
may be correct by chance.  The public training task and sealed trajectory are
allowed inputs, but the hidden task key/reference answer, fresh probe and its
answer/seed/ID, genuine outcome, and evaluator diagnostics are forbidden from
its receipt and proposal.  Independence alone is insufficient: the frozen
placebo generator must match the genuine receipt's declared distribution
conditional on every public task stratum, including value categories, byte
length/envelope, release timing class, and capability metadata, while remaining
independent of the realized local outcome and using no donor outcome from
another confirmatory block.  If that distributional contract cannot be fixed
and verified before source freeze, `ACTIVE - SHAM` is only true-feedback versus
synthetic-feedback and a new boundary review is required before execution.

Matching is enforced on admitted objects, not proposal declarations.  ACTIVE
and SHAM must have the same actual target atom-UID set, atom-kind and incidence
shape, writeset cardinality, canonical envelope length class, projection
budget, validator path, and accepted terminal.  A mismatch or one-sided
proposal rejection invalidates the complete occurrence; it cannot be dropped
or converted into an observed control outcome.

The rollback branch may retain immutable audit atoms outside the permitted
probe readset.  No audit atom, proposal transcript, outcome receipt, or staging
root may be traversable from the restored behavioral root.  The delayed outcome
is released only after all four probe-response seals and causes no transition
in this occurrence.

Fresh-probe calls receive exactly the independently rederived canonical state
projection, the precommitted `P_b`, and the fixed probe instruction.  They run
in fresh workers/sessions with network and undeclared-file access denied and
with provider/prefix caches disabled or independently shown not to create a
cross-call information path.  The response is sealed before the blind probe
evaluator scores it.

## Canonical atoms and sole responsibility owners

The future versioned schema must admit at least the following atom kinds.  The
table assigns one schema-relative accountability owner to each atom kind; it
does not make the owner the authorizer or collapse validators, executors, and
custodians into one role.

| Canonical atom kind | Sole schema-relative owner | Required typed references |
| --- | --- | --- |
| `study_randomness` | `randomness_custodian` | public future-randomness receipt, derivation version, source/prereg identities |
| `evaluator_commitment` | `evaluator_commitment_custodian` | evaluator implementation/version/key identity, sealed evaluator interface and private-material commitment |
| `block_spec` | `experiment_custodian` | schema, generator, block, public task, evaluator commitment refs; immutable before W0 |
| `probe_commitment` | `probe_custodian` | block-spec ref, hidden-key commitment, probe/answer commitments, independent seed ref |
| `placebo_commitment` | `placebo_custodian` | block-spec ref, independent randomness, pre-outcome distribution/envelope and timing commitment |
| `w0_snapshot` | `canonical_state_custodian` | block-spec/schema refs, canonical root, compiled readset, journal head, content hashes |
| `fork_incidence` | `clone_custodian` | W0 ref, opaque unassigned clone lineage, isolation receipt; no forward assignment ref |
| `block_assignment` | `assignment_custodian` | randomness, block-spec, four sealed fork refs, complete four-label permutation |
| `episode_activation` | `experiment_custodian` | block spec, probe commitment, W0, four forks, evaluator and assignment refs |
| `trajectory_contract` | `transition_contract_custodian` | activation, actor, allowed readset/action/output, evaluator-binding and seal rules |
| `trajectory_seal` | `transition_executor` | activation/contract/W0 refs, request/response, model/runtime/RNG provenance, readset |
| `permit_policy` | `permit_policy_custodian` | schema, admissible actors/effects, invariant/validator, scope and revocation rules |
| `authorization_decision` | `authorization_decision_custodian` | current authorizer, policy, actor/effect/scope, decision and decided-at refs |
| `capability_issuance` | `capability_custodian` | authorization, policy, exact scope/effect, issued-at and expiry refs |
| `revocation_status` | `revocation_custodian` | authorization/capability refs, current-as-of time, revocation evidence or absence proof |
| `evaluator_capability` | `evaluator_capability_custodian` | evaluator commitment, capability issuance, authorization decision, revocation status, exact scope and expiry |
| `evaluator_release` | `evaluator_release_custodian` | trajectory/probe seal, evaluator capability, current authorization/revocation refs, released-at and purpose |
| `hidden_outcome` | `outcome_evaluator` | trajectory seal, evaluator release, evaluator/version/key commitment, minimal outcome receipt |
| `placebo_receipt` | `placebo_custodian` | placebo commitment, independent randomness, public receipt schema |
| `outcome_credit_escrow` | `outcome_escrow_custodian` | hidden outcome, escrow capability/policy, embargo condition and later audit-release eligibility |
| `feedback_assignment` | `credit_adjudicator` | clone/arm ref, genuine/placebo/escrow source, chronology and scope |
| `grant_snapshot` | `grant_custodian` | policy, authorization, capability issuance and current revocation refs resolved for one effect |
| `revision_proposal` | `revision_proposer` | model-produced bytes, trajectory and permitted feedback refs, readset/writeset intent |
| `candidate_validation` | `revision_validator` | proposal ref, schema/invariant checks, forbidden-content scan, decision |
| `credit_decision` | `credit_adjudicator` | exact trajectory, outcome/feedback, proposal, grant, scope, decided-at refs |
| `transition_receipt` | `transition_receipt_custodian` | credit/validation/grant refs, actual readset/writeset, prior/successor, durable journal/CAS receipt |
| `restore_policy` | `restore_policy_custodian` | permit policy, capability issuance, W0-identity and admissible staging-branch scope |
| `macro_disposition` | `canonical_state_custodian` | predecessor, admitted proposal, transition receipt, successor, validator and pre-existing restore-policy ref |
| `projection_policy` | `projection_policy_custodian` | allowlisted atom kinds/refs, traversal depth, compiler/version and forbidden audit namespaces |
| `restore_transaction` | `restore_custodian` | staging successor, W0 target, grant, journal/root/readset equality receipt, allowed audit-retained refs and projection-exclusion proof |
| `behavior_projection` | `projection_custodian` | source post-arm root, projection policy, exact permitted typed readset, compiler/version hash |
| `probe_trajectory` | `transition_executor` | probe commitment, behavior projection, request/response and runtime provenance |
| `probe_outcome` | `outcome_evaluator` | probe trajectory, purpose-scoped evaluator release, hidden answer commitment, binary score |
| `block_seal` | `occurrence_custodian` | every block atom, complete nine-call ledger, terminal chronology and immutable content hashes |
| `block_analysis` | `independent_judge` | every sealed block atom, integrity status, three declared differences |
| `study_analysis` | `independent_judge` | 300 block records, frozen analysis contract, terminal and nonclaims |

Any persistent seal, grant, revocation, assignment, incidence, capability,
restore, or permission-bearing relation must itself be an owned canonical atom,
not an ephemeral pointer hidden in another payload.  The final schema may split
a listed kind more finely but cannot merge away its distinct lifecycle or
authorization effect merely to reduce the atom count.

For every admission or restore effect `e`, the executor must verify:

```math
Inv_sigma(S,e,S') and Permit_sigma(S,e)
and SingleOwner_sigma(writeset(e)).
```

`Permit_sigma` binds a current, separately owned authorizer/grant decision to
the exact actor claim, readset, writeset, scope, capability, decision time,
expiry/revocation state, validator, provenance, and restore path.  An owner,
state custodian, transition executor, or credit adjudicator cannot infer
permission from its own role name.  A new DNRD-5 fail-closed transaction gate
must resolve the policy, current authorization, capability, and revocation
state immediately before each CAS/journal submission; bind that resolution and
its descriptor to the transition receipt; and reject drift between resolution
and submit.  Generic canonical-atom V2 authorization fields and the existing
current-state-permit evidence checker do not themselves issue or enforce this
commit capability.

For every state-changing revision or restore scope, the actual principal at
`authorization_decision.authorizer` must be unequal to the actor claim, the
canonical-state custodian, the restore custodian, the credit adjudicator, and
the authorization-decision-record custodian.  This principal inequality is a
schema/invariant check over the exact effect, not an inference from distinct
role labels.  Any deliberately self-authorized non-learning fixture belongs in
a separately declared test scope and cannot support the DNRD-5 learning claim.

## Sealing chronology and allowed information flow

Every block obeys this order:

```text
study randomness and block/task/evaluator commitment
-> probe/placebo commitments
-> W0 snapshot and four opaque unassigned forks
-> arm-permutation commitment over the sealed forks
-> episode activation and trajectory contract
-> pre-outcome call and trajectory seal
-> evaluator capability release and hidden-outcome seal
-> outcome-credit escrow, placebo-receipt opening, and four feedback-assignment seals
-> four proposal calls and proposal seals
-> arm-specific validation, credit, admission/quarantine/restore
-> four independently rederived behavior projections
-> four randomized-order probe calls and response seals
-> blind probe outcomes
-> delayed-outcome audit release
-> block seal
```

The probe identity and hidden answer are committed before the training outcome
is opened.  Commitment does not mean disclosure: the transition, revision,
state compiler, and model cannot read those private bytes.
The escrow, placebo receipt, and per-clone feedback assignments are immutable,
read-only proposal inputs once sealed; proposal calls cannot create or rewrite
their own feedback source or capability.

| Consumer | Allowed inputs | Forbidden inputs before its seal |
| --- | --- | --- |
| Training model | `X_b`, permitted `W0_b` projection, fixed instruction/RNG | probe, hidden task/answer, evaluator/outcome, placebo, arms/clones, other blocks |
| Training evaluator | sealed answer/action and private task key | arms/clones, state representation, proposal/probe material |
| Proposal model | sealed trajectory projection and its one assigned feedback projection | arm label, clone ID, probe/answer, alternate feedback, evaluator diagnostics, other state |
| State transition | proposal, validation, exact effect/grant refs | probe/answer, undeclared files/network/cache, another clone's state |
| Probe model | one behavior projection, `P_b`, fixed instruction/RNG | raw trajectory/outcome/proposal/audit refs, arm/clone IDs, other sessions |
| Probe evaluator | sealed probe answer and private answer key | arm/clone/order, canonical state, feedback type, model diagnostics |
| Independent judge | all artifacts only after occurrence sealing | any write or model/evaluator influence |

The judge independently reconstructs every allowed model-input byte from its
attested readset.  A mismatch is not a statistical observation; it is a
protocol validity failure.

## Causal model, potential outcomes, and assumptions

Let `G_b` be the random arm mapping, `U_b` the independent placebo feedback,
`R_b(a)` the arm-specific LLM proposal, `M_b(a)` the behaviorally readable
state, `Q_b(a)` the probe response, and `Z_b(a) in {0,1}` the blind score.
The intended DAG is:

```text
B_b=(K_b,X_b,P_b,W0_b) -> T_b -> Y_b
T_b, assigned_feedback(Y_b or U_b or escrow), G_b -> R_b(a)
R_b(a), Permit_b(a), G_b -> M_b(a) -> Q_b(a) -> Z_b(a)
P_b -------------------------------------> Q_b(a) -> Z_b(a)
```

`G_b` intentionally selects which assigned-feedback projection reaches each
proposal call, so its declared path to the proposal input is part of the
intervention.  It has no route to a probe-model input, probe evaluator, or score
except through the arm-specific validated canonical state projection.  `Y_b`
may reach a probe only through a valid proposal, credit decision, admitted
macro-disposition, and that projection.

For opaque clone `c`, `Z_bc(a)` is its potential probe outcome under arm `a`.
Within each block the four sealed clone IDs are exchangeable before `G_b`, and
all four treatments have probability `1/4`.  The observed block contrast is
the active clone score minus the corresponding control clone score.  The
target population is only the frozen independent block generator and runtime,
not arbitrary tasks or models.

Identification requires consistency, positivity, pre-arm clone exchangeability,
no cross-clone/block/session interference, evaluator validity and blindness,
probe independence, treatment adherence, the exclusion path above, exact W0
restoration, and independently generated blocks.  Each is a declared trust
condition or adversarial test target, not a result inferred from a small
p-value.

## Estimands, inference, and power

For controls `S=OUTCOME_INDEPENDENT_SHAM`, `D=DELAYED_NO_CREDIT`, and
`R=EXACT_W0_ROLLBACK`, define:

```math
D_bj = Z_b(ACTIVE) - Z_b(j) in {-1,0,1},
hat_tau_Aj = (1/300) sum_b D_bj,
j in {S,D,R}.
```

`tau_AS` is the primary estimand.  `tau_AD` and `tau_AR` are secondary
mechanism estimands required for the full causal-mechanism claim.  All 300
complete blocks remain in every count and descriptive table; conditioning on
discordant pairs in the exact sign test does not redefine `N`.

The confirmatory gate uses three one-sided conditional paired randomization
tests.  For contrast `j`, let `m_j` be its discordant-block count and `w_j` the
number favoring active.  Under the pairwise sharp null and the frozen
within-block label swap:

```math
p_j = 2^(-m_j) sum_{k=w_j}^{m_j} choose(m_j,k),
p_j_adjusted = min(1, 3 p_j).
```

The `>=` tail and all ties are fixed.  Bonferroni at familywise one-sided
`alpha=0.05` is deliberately conservative and supports three individually
controlled findings plus simultaneous reporting.  It is stronger than needed
for a single intersection-union conjunction, but simpler to audit and does not
depend on an unknown contrast correlation.  An equicorrelated normal max-stat
calculation may be reported as sensitivity analysis only; it is not a success
gate.

For magnitude, the judge reports each `hat_tau_Aj`, discordance, sample
variance, and an explicitly **asymptotic** one-sided Bonferroni simultaneous
lower bound

```math
LCB_j = hat_tau_Aj - z_(1-0.05/3) s_j / sqrt(300).
```

It must not call this an exact randomization confidence interval.  A bounded
`CAUSAL_MACROPLASTICITY_GO` requires complete integrity, all three adjusted
exact p-values at most `.05`, and all three `LCB_j > 0`.  If only the primary
passes, the terminal is `PRIMARY_SIGNAL_MECHANISM_INCOMPLETE`, not the full
claim.  A valid failure is `VALID_CAUSAL_NO_GO`; it is no evidence of absence
and cannot authorize a retry.  The exact p-values reject pairwise sharp-null
randomization hypotheses; they do not exactly test the weak null
`tau_Aj <= 0`.  Directional average-effect evidence comes from the separately
labeled asymptotic lower bounds, so the GO requires both layers.

The reviewable arithmetic prototype is
[`_research/dnrd5/analysis.py`](../../_research/dnrd5/analysis.py), with frozen
edge cases in
[`analysis_v1.json`](../../_research/dnrd5/vectors/analysis_v1.json).  It
labels its exactness precondition `NOT_VERIFIED_BY_THIS_ARITHMETIC_MODULE`.
It may emit only `ARITHMETIC_*_PENDING_INTEGRITY` terminals, including
`ARITHMETIC_GO_PENDING_INTEGRITY`; it cannot emit a scientific GO.  Only the
later independent production judge may issue the scientific terminal after
verifying frozen assignment, deterministic potential outcomes, sealed inputs,
and the complete production integrity gate.  Its canonical output binds both
the expected block-ID universe and normalized observed rows by SHA-256; those
hashes identify the arithmetic inputs but do not themselves verify their
scientific integrity.  Its input keys use the four canonical arm identifiers
verbatim; no judge-side alias translation is permitted.

The planning alternative is `tau_AS=tau_AD=tau_AR=0.15`.  **This is not an
observed-effect pass floor and does not support a claim that the true effect is
at least 15 percentage points.**  Such a magnitude claim would require testing
a positive null margin and planning against a larger alternative.

For the finite-`n` planning gate at `q=.50` and `delta=.15`, the assumed iid
block-level marginal law is `P(D=+1)=13/40`, `P(D=-1)=7/40`, and
`P(D=0)=20/40`.  Under that law, the exact marginal single-contrast success
probability at `n=300` is
`p_single ~= .9354136401`.  Without assuming any dependence structure among
the three contrast-success events, the Fréchet lower bound (obtained by a union
bound on their failures) is `max(0, 3 p_single - 2) ~= .8062409204`.  The
corresponding finite-`n` lower bound is below `.8` at `n=297`; `n=298` is the
first integer at or above `.8`.  The design fixes 300 blocks as a small margin
above that threshold, not as a claim that the three contrasts are independent.

The checked-in calculator
[`_research/dnrd5/power_planning.py`](../../_research/dnrd5/power_planning.py)
is labeled `EXACT_FINITE_N_COMBINED_MARGINAL_GATE_PLANNING /
NOT_INFERENTIAL_EVIDENCE`.  Its finite-`n` values are exact under the declared
three-point marginal planning law; they are still prospective design
calculations, not observed evidence.  Normal and correlation-based rows are
labeled `NORMAL_APPROXIMATION_SENSITIVITY_ONLY`, including every `rho=0`
calculation; `rho=0` is not claimed conservative.  `q`, the marginal planning
law, and every dependence scenario remain assumptions.  The preregistration
must publish the full scenario grid, and no valid negative result may be
promoted to evidence of absence, especially outside it.

## Integrity checks and terminals

Before source freeze, one versioned end-to-end contract vector must be consumed
unchanged by registration, executor, evaluator gateway, state runtime, and the
independent judge.  Producer and judge parse and derive it independently.  It
must contain one complete production-shape accepted path and adversarial cases
for at least:

- canonical JSON/order/hash bytes, sole ownership, typed-reference closure,
  grant/revocation and `Permit_sigma` scope;
- task/probe/placebo independence, evaluator blinding, outcome capability
  release/escrow, and chronology of every seal;
- wrong trajectory/outcome binding, true outcome in sham, probe leakage,
  hidden labels in any model input, and evaluator diagnostics in state;
- stale CAS, forbidden writes, duplicate calls, call-cap overflow, invalid
  assignment, clone/readset mismatch, and another clone's state;
- active-state/W0 swap, placebo-state swap, opaque arm-label swap, revoked
  outcome capability, exact restore, journal recovery, and fresh-runtime replay;
- network/file/session/cache attempts and independent reconstruction of every
  allowed model-input byte;
- a disjoint production-shape qualification vector showing whether identical
  request/runtime/RNG bytes reproduce identical model output despite provider,
  kernel, and scheduling state; absent that capability, every exact-test label
  must be downgraded before source freeze;
- exact conditional-test vectors, large integer binomial tails, Bonferroni
  adjustment, asymptotic lower-bound edge cases, and fixed tie rules.

Before the semantic occurrence marker, identity, chronology, manifest,
runtime, remote-head, evaluator, assignment, or vector failures are
`PREMARKER_REFUSAL` and make no model call.  After the marker, any unaccounted
call, source/runtime/model drift, hidden leakage, evaluator unblinding,
cross-arm interference, unauthorized or noncanonical write, invalid
randomization, nonexact restore, missing provenance, or seal mutation makes the
whole occurrence `VOID_PROTOCOL` with no efficacy analysis.

A validly sealed operational failure or missing probe/evaluator receipt makes
the whole occurrence `INCONCLUSIVE_OCCURRENCE`; there is no complete-case
analysis, replacement block, resume, second pulse, or rerun.  A complete valid
occurrence that misses the scientific rule is `VALID_CAUSAL_NO_GO`.  Raw block
counts, outcomes, discordance, effects, intervals, and every terminal are
published under the same evidence-retention rule.

## Pre-observation commitment without repeated user hash echoes

No manual exact-hash echo from the user is a DNRD-5 gate.  The user's broad
instruction to continue the bounded scientific program authorizes the
operational preparation, one frozen occurrence, independent judgment, and
honest recording under the finite limits above.  Source A will normalize that
scope without claiming a byte-exact transcript or speaker-identity proof.

Pre-observation integrity instead requires:

1. a clean public Source-A commit containing the complete instrument, source
   manifest, contract vector, and this boundary, followed by one uniquely
   selected first-attempt successful push CI receipt;
2. a direct-child Source-B commit changing only the canonical preregistration,
   followed by its own uniquely selected first-attempt successful push CI
   receipt; and
3. a public future-randomness pulse after both commitments, used for block,
   clone, arm, call-order, and per-call seed derivations before one marker and
   one occurrence.

This is operational authorization and an auditable chronology.  It is not
scientific evidence, independent human review, a fabricated user signature,
human-subject authorization, or permission for effects beyond the declared
local experiment.

## Next implementation boundary

The next legitimate work is the new `_research/dnrd5/` research program and
its tests.  It may reuse generic canonical-atom V2 canonical JSON and content
hashing, owner/type/reference/cardinality checks, CAS, journal durability, and
recovery primitives from `src/hswm/effect-runtime/`.  Those primitives do not
provide W0 fork identity, current Permit resolution, hidden-label access
control, evaluator process/root isolation, network/filesystem/session/cache
sandboxing, semantic leakage scans, model-call accounting, behavior-projection
non-traversability, or independent input reconstruction; DNRD-5 must implement
and test those contracts explicitly.  It must not reuse or relabel DNRD-4/S1's
response-independent routing learner, scorer, fixed task family, executor, or
judge: those contracts explicitly do not implement causal learning.

No source freeze or preregistration is allowed until the task family,
independent evaluator boundary, schema/owner/Permit contracts, nine-call
ledger, exact arm assignment, information-flow sandbox, statistical judge,
and complete end-to-end vector are implemented and independently reviewed.
Tests are readiness evidence instruments, not a DNRD-5 result.

Method anchors for the later frozen analysis are paired-experiment average
effect inference ([Fogarty 2018](https://doi.org/10.1093/biomet/asy034)),
multiple-treatment stratified randomization
([Bugni, Canay, and Shaikh 2019](https://doi.org/10.3982/QE1150)), and the
distinction between sharp-null randomization tests and average-effect
confidence statements.  The checked-in equations and future contract vectors,
not a library default or citation alone, govern the occurrence.
