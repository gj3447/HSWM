# HSWM-DNRD-5 exactness policy amendment

- Date: 2026-08-28
- Status: `SOURCE_A_PRECONDITION / EXACT_PVALUE_REQUIRED / NO_INFERENCE_FALLBACK`
- Scope: DNRD-5's inferential authorization only
- Governing design: [R2 causal macroplasticity design](HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md)
- Historical R2 commit: `7ff9454e3f274183bdd9c1465ad68b0ef91cb8ec`
- Historical R2 file SHA-256:
  `660f97baefe5dbb46a3a5764255b1bbebca2baf72a4623e28ab2342c3196533a`

## Authority and priority

This amendment resolves the R2 provision that allowed a possible downgrade from
finite-sample exact inference to an unspecified “exchangeability/asymptotic”
status. It does not edit, reinterpret, or invalidate the historical R2 design.
For every Source-A freeze decision after this amendment, this document takes
priority over that unresolved downgrade provision.

The policy is **exact-test-required with no inferential fallback**.  The three
finite-sample exact sign-test components remain mandatory.  The R2 normal
Bonferroni lower bounds also remain separate, mandatory directional components
of the conjunction; they do not replace a failed or unauthorized exact test.
Likewise, an exact p-value cannot replace an unqualified lower-bound component.

No standalone asymptotic fallback is authorized by the current DNRD-5
instrument.  A future fallback requires a separately reviewed, versioned design
revision and its own prespecified estimator, dependence model, standard-error
construction, missingness rule, decision thresholds, terminals, and
adversarial vectors.  The currently implemented normal lower bounds are not
that fallback.

## Target identity, current evidence, and conceptual delta

HSWM's target identity remains one token-native LLM-function macro-neural
network: schema-approved canonical atoms and typed references form its evolving
hypergraph, and outcome-bound, owner-valid transitions are the proposed
continuous-learning loop. DNRD-5 is a bounded causal test of one possible
outcome-to-revision-to-fresh-probe path within that identity; it neither defines
HSWM as separate harness/world-model/learner subsystems nor establishes that
the path has occurred.

Current evidence is design-instrument evidence only. No DNRD-5 model call,
occurrence, outcome, state admission, causal effect, or HSWM learning result
exists. The conceptual delta of this amendment is narrow but necessary: an
arithmetic exact sign tail and an asymptotic normal lower bound cannot be
silently substituted for one another, and passing finite qualification checks
cannot be relabeled as proof of their identification assumptions.

## Required inference layers and assumption profiles

Let the four opaque pre-arm clone lineages in block \(b\) be assigned by the
frozen uniform four-label permutation \(G_b\). For each control
\(j\in\{S,D,R\}\), DNRD-5's sign tail applies only under the pairwise sharp
null and the frozen within-block ACTIVE/control label-swap law. Its arithmetic
is

\[
p_j=2^{-m_j}\sum_{k=w_j}^{m_j}{m_j\choose k},\qquad
p_{j,\mathrm{adj}}=\min(1,3p_j),
\]

where \(m_j\) is the discordant-block count and \(w_j\) is the count favoring
ACTIVE. This is not an exact test of the weak average-effect null
\(\tau_{Aj}\leq0\).

The exact-test assumption profile contains distinct claims that must not be
collapsed into one word such as “deterministic” or “exchangeable”:

1. The frozen post-Source-B beacon selection rule and study binding induce the
   declared uniform `S4` arm permutation and pairwise ACTIVE/control label-swap
   law over the exact 300 blocks.  The producer and judge must independently
   agree on every permutation and nine-call logical slot for every receipt
   accepted by the frozen receipt parser and on an adversarial conformance
   corpus.  Beacon uniformity and the derivation/PRF law remain explicit
   assumptions; one realized beacon cannot prove them.
2. Each clone has a well-defined potential outcome under its assigned arm and
   satisfies consistency.  DNRD-5 deliberately requires deterministic response
   generation inside the frozen model/runtime/request/RNG/isolation boundary as
   a strong sufficient-condition policy.  Finite replay observations can
   falsify that profile but cannot prove behavior over unobserved provider,
   kernel, cache, or scheduling states.
3. The four opaque clone lineages are exchangeable before assignment and there
   is no arm/clone leakage or cross-clone, cross-block, session, cache,
   filesystem, network, or worker-history interference.  A finite isolation
   control profile can detect declared violations; it cannot prove the absence
   of every possible path.
4. Evaluator validity and blindness, exact treatment adherence, complete
   request-byte reconstruction, exact W0 restoration, and the bans on retry,
   resume, replacement, cache substitution, undeclared calls, and outcome-based
   exclusion all hold for the sealed occurrence.

The R2 lower-bound component has a separate directional-inference assumption
profile: the 300 block contrasts must support the prespecified block-level
normal approximation, variance estimate, and simultaneous Bonferroni coverage.
Provider reproducibility or a valid label-swap law does not establish these
block-cluster conditions.  Source A cannot qualify the scientific GO unless
both profiles have frozen evidence standards and retained assumptions.

## Qualification evidence and chronology

Qualification evidence is evidence capable of falsifying or supporting an
assumption profile under a declared finite boundary; it is not proof that the
profile is universally true.  The phases are therefore separated as follows.

### Q — disjoint instrument qualification before Source A

Any response-reproducibility measurement must first have its own frozen
qualification protocol: exact disjoint corpus, call classes, number of cases
and replicates, response comparator, endpoint/model/runtime/TLS and isolation
descriptors, randomized call order, per-attempt START/terminal evidence,
fixed budget, and zero-retry rule.  Its calls, roots, tasks, and outputs are
namespaced as qualification-only, can never enter the 300-block population, and
cannot be treated as DNRD-5 occurrence calls or pilot effect data.

Before the first Q call, a `Q0` commitment must be immutably published from a
specified source commit/tree and first-attempt successful CI build.  Its exact
bytes bind the protocol and terminal/missingness rules, corpus IDs, replicate
count and comparator, endpoint/model/runtime/TLS descriptors, fixed budget,
call-order rule and any randomness source, verifier source/build hash, and
evidence-root genesis.  A `Q_START_MARKER` must bind `Q0` before any gateway
START record; the only accepted chronology is `Q0 -> Q_START_MARKER -> all Q
START/terminal records -> Q closure`.  Source A later binds both `Q0` and the Q
closure.  A plan written or changed after observing Q output is ineligible.

A separate namespace is not evidence of provider-state separation.  Unless the
Q protocol establishes separation from the later occurrence's provider-side
cache, session, worker, and account history, its calls are only a finite
response-reproducibility falsification probe; they cannot support the
occurrence no-interference profile.  An unclosed shared-provider path remains a
Source-A blocker.

No such call protocol is currently frozen or authorized.  When one is later
frozen, a passing record may say only
`REPRODUCED_ON_FROZEN_QUALIFICATION_CORPUS_UNDER_DECLARED_BOUNDARY`; it may not
say that provider, kernel, cache, or scheduling determinism was proved.  The
isolation profile must analogously report tested controls and observed
violations, not `NO_INTERFERENCE_PROVED`.  A single request hash, provider
receipt, synthetic lifecycle vector, structural production vector, or existing
DNRD-4 qualification cannot substitute for these records.

### A — source-freeze decision

Source A must bind the exact historical R2 bytes, this amendment's canonical
bytes and SHA-256, the qualification plans and evidence, the frozen independent
verifier and conformance vectors, the future-receipt parser/selection rule, the
300-block universe, canonical encoding, build/runtime identities, and all
retained assumptions.  It cannot contain the later Source-B commit, selected
beacon receipt, occurrence W0/forks, responses, or occurrence result.

The independent verifier closure must bind its source commit/tree, selected
build-output SHA-256, semantic allowed-import graph, cross-language canonical
corpus, and the versioned end-to-end actual-byte evidence schema.  Its
conformance cases must open and descriptor-check the TS lifecycle, W0, Permit,
durable journal records and the Python gateway/Q records.  The present
synthetic structural vectors do not satisfy this closure and cannot qualify
Source A.

The exact Source-A decision outcomes are:

- `SOURCE_A_REFUSED_EXACTNESS_UNQUALIFIED` when the exact-test assumption
  profile lacks its prespecified supporting evidence or has a falsifying result;
- `SOURCE_A_REFUSED_LCB_UNQUALIFIED` when the directional lower-bound profile
  lacks its prespecified justification; and
- `SOURCE_A_INSTRUMENT_QUALIFIED_FUTURE_OCCURRENCE_EVIDENCE_REQUIRED` only when
  both profiles and the complete instrument pass their frozen qualification.

These are source-freeze decisions, not occurrence terminals.  A refusal
authorizes no Source-A freeze, preregistration, future-randomness selection, or
DNRD-5 occurrence model call.  Q calls are allowed only under the separately
precommitted Q0 protocol and are never retroactively authorized by Source A.  A
refusal does not erase already sealed, separately budgeted Q-phase
qualification calls.  A qualification decision never authorizes efficacy
analysis or reinterpretation of the lower bound as a fallback.

### B — post-Source-B premarker and occurrence evidence

After Source B and before the marker, the occurrence preflight must verify the
actual future receipt and chronology, independently rederive assignment and the
logical 2,700-call plan, bind the single selected root, check initial W0/forks
and current build/runtime/model/evaluator identities, and establish zero prior
occurrence dispatch.  Later proposal and probe request bytes depend on earlier
sealed outputs, so they cannot all exist before the first call; the sole
dispatcher must reconstruct and seal each request immediately before its one
allowed call, and the independent judge must rederive all of them after block
closure.

A Phase-B failure before the marker is `PREMARKER_REFUSAL`, not a Source-A
decision.  After the marker, an observed identity drift, forbidden path,
unaccounted call, retry, leakage, interference, unauthorized write, or restore
failure is `VOID_PROTOCOL`.  Unobservable assumptions remain named assumptions;
they are not promoted to facts by an absence of detected violations.

Source-A and Source-B bundles must use the exact bounded canonical-JSON
implementation and a shared cross-language adversarial corpus.  The present
Python randomization modules' ordinary `sort_keys=True` serialization is not
that cross-language contract; it must be migrated or its accepted keys must be
formally restricted and tested before Source A.

## Placebo theorem is conditional, not custody proof

For a fixed complete model-visible pre-feedback history \(H\), including the
public task stratum, sealed trajectory, fixed instruction/RNG/runtime
projection, and declared timing/capability projection, the checked-in placebo
lemma states the following conditional algebra:

\[
P(\theta=t,U=u\mid H)=1/4\quad\text{for }t,u\in\{0,1\}
\quad\Longrightarrow\quad
E_H(1\{c=\theta\})\overset{d}{=}E_H(U).
\]

Here \(c\) is the sealed chosen hypothesis, \(U\) is the placebo bit, and
\(E_H\) is the common canonical feedback-envelope encoder. Thus the genuine
and placebo envelopes have identical conditional byte distributions under the
stated law. Choice-only conditioning is insufficient if the visible trajectory
contains information about \(\theta\).

Neither the conditional law for \(\theta,U\) nor the beacon/PRF uniformity law
is proved by SHA-256 domain separation, canonical hashes, a source receipt, or
one occurrence. They are explicit design assumptions. Before an occurrence can
be integrity-valid, the independent judge must instead verify the available
evidence relevant to those assumptions: separately committed sources and
custodians, pre-outcome placebo commitment and opening, exact history \(H\),
no genuine-outcome donor path, no outcome/probe/evaluator leakage into sham,
and the actual timing/capability bindings. Passing that verification does not
turn the assumptions into empirically proved randomness laws.

## Analysis layers and non-substitution rule

The exact sign test and the lower confidence bound answer different questions
under different assumptions:

- The sign tail is finite-sample exact only for the stated sharp-null,
  label-swap randomization law and the retained deterministic-potential-outcome,
  exchangeability, consistency, and no-interference assumptions.  Frozen
  qualification evidence may support or falsify that profile; it does not prove
  the assumptions.
- The Bonferroni lower bound is an asymptotic normal approximation for the mean
  block contrast. It requires its own justified block-cluster dependence and
  variance conditions; it is not an exact randomization interval or test.

The arithmetic module may continue to produce only
`ARITHMETIC_*_PENDING_INTEGRITY` outputs. It cannot issue a scientific GO.
Even a successful complete Source-A instrument qualification may issue only
`SOURCE_A_INSTRUMENT_QUALIFIED_FUTURE_OCCURRENCE_EVIDENCE_REQUIRED`; it is not
an exactness result, custody result, occurrence, causal finding, or HSWM
learning result.

## Fixed population, exclusion, and stopping

The analysis population is exactly `DNRD5-BLOCK-0001` through
`DNRD5-BLOCK-0300`. Each complete block contributes all four canonical arm
outcomes to every descriptive table and paired contrast. Discordance conditions
the sign tail; it never changes \(N=300\). No block, arm, call, or contrast may
be removed because its outcome, response, direction, discordance, or apparent
quality is unfavorable.

After a qualified Source A and Source B exist but before an occurrence marker,
any occurrence-specific identity, manifest, source, assignment, runtime, or
vector failure is `PREMARKER_REFUSAL` and makes no occurrence model call.
Q-phase and Source-A decisions retain the separate taxonomy above.  After the
marker, any observed integrity failure—including invalid randomization,
unaccounted call, request/runtime identity drift, hidden leakage, cross-arm
interference, noncanonical or unauthorized write, or nonexact restore—voids the
whole occurrence as `VOID_PROTOCOL`; no efficacy analysis is allowed.  Sealed
operational missingness produces
`INCONCLUSIVE_OCCURRENCE`, never complete-case analysis. There is no replacement
block, retry, resume, second future pulse, or rerun.  If a complete
integrity-valid occurrence has the R2 primary-only pattern, its terminal remains
`PRIMARY_SIGNAL_MECHANISM_INCOMPLETE`.  Other complete integrity-valid
300-block occurrences that fail the frozen scientific rule are
`VALID_CAUSAL_NO_GO`, not evidence of absence.
