# HSWM-DNRD-5 implementation-readiness review

- Date: 2026-08-28
- Review scope: post-R2 task, evaluator, randomization, lifecycle, provider,
  schema, lifecycle-to-atom alignment, local durable-Permit, and structural
  occurrence-preflight candidate slices
- Decision: `NOT_READY_FOR_SOURCE_FREEZE / NOT_READY_FOR_PREREGISTRATION / NO_MODEL_CALLS`
- Scientific status: `DESIGN-INSTRUMENT PROGRESS / UNMEASURED / NO EFFECT RESULT`
- Governing design:
  [`HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md`](HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md)
- Exactness policy:
  [`HSWM_DNRD_5_EXACTNESS_POLICY_AMENDMENT_2026-08-28.md`](HSWM_DNRD_5_EXACTNESS_POLICY_AMENDMENT_2026-08-28.md)

## Canonical role and present evidence

HSWM's target remains one token-native LLM-function macro-neural network whose
evolving canonical hypergraph is simultaneously living harness, world model,
and continuous learner.  DNRD-5 asks one bounded causal question inside that
identity: can a sealed token trajectory receive independently attributable
feedback, cause an LLM-proposed and currently permitted macro-disposition
revision, and thereby change a fresh hidden-probe transition?

The present repository does **not** answer that question.  DNRD-1 through
DNRD-4S1 yielded no verified effect, and DNRD-5 has not run.  The additions
reviewed here are instruments and mathematical design checks.  A KG, schema,
runtime, test, hash, CI job, or passing synthetic vector remains a bounded
projection or evidence instrument, not HSWM cognition or learning.

## Scientific task delta now implemented

The new task family is not a renamed DNRD-4 route task.  Every block publishes
two pointwise-different four-token hypotheses, `H0` and `H1`, while privately
committing a hidden bit `theta`, a distinct held-out probe, its answer, and an
separately domain-separated candidate placebo bit.  Its conditional
independence is not established by domain separation.

The pre-outcome model response must choose exactly one hypothesis and emit the
corresponding training token.  The private evaluator returns only whether that
choice matched `theta`.  Under the explicitly assumed fair hidden-bit law, the
choice and genuine correctness bit uniquely identify `theta`.  A proposal
using an independent fair placebo bit receives the same one-bit public shape
but identifies the correct hypothesis only half the time.  The held-out probe
opens after the proposal/state phase and tests application of the selected
hypothesis at another input.

An implementation-independent `2 x 2 x 2` enumeration now checks this
identification algebra exactly with `Fraction` arithmetic.  It conditions on
both possible arbitrary pre-outcome choices rather than assuming that the
model chooses `H0` and `H1` equally.  In the idealized oracle reference, ACTIVE
scores one and each control has mean one half.  That theoretical half-point
contrast is **not** the preregistration's `.15` planning alternative and is not
an observed effect.

The exact feedback-envelope lemma now fixes the complete model-visible
pre-feedback history `H`, including the sealed trajectory and fixed projection
metadata.  Under the explicit assumption
`P(theta=t, U=u | H) = 1/4`, the genuine bit
`Y = 1{choice=theta}` and placebo bit `U` are conditionally independent fair
bits, and the common canonical encoder gives identical conditional byte
distributions.  An executable counterexample shows why conditioning on choice
alone is insufficient when the trajectory reveals information about `theta`.
This corrects the earlier, weaker conditioning claim; it does not establish
that production entropy and custody satisfy the assumed law.

The enumeration and envelope lemma deliberately retain four boundaries:

- domain-separated SHA-256 provides computational concealment; it does not
  prove mathematical conditional independence of the hidden and placebo laws;
- no present production record proves independent entropy/custody, pre-outcome
  commitment and opening, evaluator-to-genuine binding, no donor outcome, or
  equality of every timing/capability field in the complete history `H`;
- a fixed algorithm can reproduce the finite two-hypothesis behavior, so this
  task cannot establish mechanism uniqueness; and
- delayed/W0 and rollback equality in the enumeration use an idealized fixed
  W0 probe policy.  Actual model, RNG, provider, and restored-state behavior
  must be measured and sealed rather than inferred from the table.

## Implemented readiness instruments

The checked-in candidate slice now contains:

1. Pure task construction with exact 300 block IDs, strict public/private
   records, pointwise-different hypotheses, unbiased rejection sampling for
   train/probe selection, content commitments, and cross-private consistency
   checks.
2. Minimal training and blind-probe evaluator functions.  Their records expose
   no hidden answer or diagnostics, but they are not yet an isolated production
   process or capability boundary.
3. A declared source-blind synthetic projection schema with identical genuine
   and placebo key sets, canonical byte length, and trajectory binding, plus the
   exact conditional encoder lemma and its choice-only-conditioning
   counterexample.  It is not wired to a real evaluator receipt.  Distributional
   equality in production still rests on the unverified conditional latent law,
   custody, chronology, and cryptographic assumptions.
4. A future-randomness producer that internally derives the only canonical
   fork order, four-arm permutation, opaque proposal/probe order, and per-call
   seed commitments for all 300 blocks and exactly 2,700 call slots.  The old
   caller-supplied fork-order manipulation path was removed.
5. A separately implemented randomization consumer that shares no producer
   helpers or constants at runtime and reconstructs all canonical plan bytes.
   Reordering or rehashing forks, arms, call slots, or RNG commitments is
   refused.
6. A strict canonical lifecycle validator and shared Python/TypeScript vector
   for the complete R2 seal order at the structural lifecycle-artifact level
   only, including exactly one trajectory call, four opaque proposal calls,
   four opaque fresh-probe calls, and terminal block closure.  Its synthetic
   descriptors prove neither custody nor a provider/evaluator/state execution
   connection; the vector is contract evidence, not an occurrence.  The exact
   lifecycle cardinality is 15 events and 59 artifact descriptors, not 53.
7. A DNRD-5 canonical-atom V2 schema with 37 schema-approved kinds, exactly one
   responsibility owner per kind, typed references, exact four arms,
   actual-principal inequality, strict provenance, and a dedicated persistent
   `capability_consumption` atom.  An alignment audit found that delayed outcome
   disclosure has no owned canonical kind in this v1 schema.  The v1 identity
   is preserved; this omission must be repaired under a successor schema rather
   than by silently changing v1 semantics.
8. A pure fail-closed local non-human `Permit_sigma` resolver, frozen revision
   envelope, ACTIVE/SHAM admitted-shape matcher, W0/four-fork identity validator,
   rollback projection validator, and exact nine-call manifest validator.  Each
   terminal states its bounded nonclaim.
9. An internal durable-Permit candidate that re-reads the exact journal head and
   state hash, binds the actor/scope/capability/time/read/write/target sets,
   reads and compares the durable policy/authorization/capability/revocation/
   grant payload bytes and their exact typed-reference closure, and places
   deterministic one-shot consumption in the same journal CAS as admission or
   restore.  A documented CAS-conflict loser is re-read and classified as an
   already-consumed nonce only when the exact validated winning atom exists.
   Memory admission/replay, concurrent one-winner, normal file reopen, and
   stale/altered-input integration tests pass.  The public generic durable
   `submit` now fails closed for the DNRD-5 schema with
   `DNRD5_PERMIT_DISPATCH_REQUIRED`; the Permit dispatcher alone invokes a
   module-held commit capability that is absent from the package root.  A
   static textual allowlist test fails if the exact capability identifier
   occurs in any other checked `src/` TypeScript file.  This closes the ordinary
   checked-source/package-root durable bypass.  It is not yet an
   occurrence preflight, a proof against arbitrary modified repository source,
   a crash-fault proof, a global capability ledger, or a trusted external
   authority/time service.
10. A client-side OpenAI-compatible provider gateway that constructs the exact
    request internally, persists content-addressed request/projection/response
    bytes and a hash-chained START/terminal ledger, validates a bounded closed
    response schema, and supplies client-observed evidence plus a validator for
    closing the exact `1 + 4 + 4` call grammar.  No occurrence orchestrator yet
    binds it to lifecycle/evaluator/state evidence.  An unterminated START
    permanently closes that evidence root to later dispatch.  Loopback tests
    exercise real HTTP bytes; no real provider call has occurred.
11. A synthetic structural production contract vector with R2 lifecycle,
    W0/rollback placeholders, and Permit fields.  Its terminal explicitly says
    it is neither execution nor integrity evidence, and it is not yet joined to
    the provider, evaluator, state, and custody records in one end-to-end vector.
12. A pure two-stage Source-A/Source-B structural preflight scaffold.  It pins
    the historical R2 and exactness-amendment identities, exact 300-block
    universe, ordered retained-assumption profile, and Q0-to-Q-closure binding;
    binds caller-supplied Source-B, beacon-selection, build, runtime, and
    no-prior-dispatch descriptors; independently rebuilds both complete
    2,700-slot randomization plans; and derives the occurrence-root descriptor
    from the exact Source-A binding, canonical Source-B descriptor, beacon
    receipt, future-randomness digest, and study binding.  Both success and
    typed-refusal surfaces fix dispatch authority to false and budget to zero.
    Its terminals are deliberately `*_STRUCTURAL_*_CALLER_DESCRIPTORS_ONLY`,
    and `source_freeze_eligible` is always false.  It performs no Git, CI,
    beacon-cryptography, trusted-time, external-authority, gateway, marker, or
    durable-root I/O and therefore establishes none of those facts.  The large
    plan blobs now use the separate, plan-specific
    `hswm-dnrd5-plan-json/v1` contract rather than widening bounded
    `hswm-canonical-json/v1`.  Two independently implemented Python codecs and
    one independently implemented TypeScript codec consume one content-addressed
    adversarial KAT over the exact restricted key/value and byte domain.  The
    two Python paths rederive and compare two complete 300-block, 2,700-slot
    plans.  A third, independently implemented TypeScript randomization path now
    also rederives both full plans byte-for-byte, including raw byte length,
    blob SHA-256, and root plan SHA-256, without importing Python or process
    execution.  This closes the design-instrument cross-language allocation
    rederivation seam.  It does not bind the selected Source-A source/tree,
    build output, semantic import graph, or actual-byte evidence schema and is
    not source-freeze qualification, occurrence evidence, efficacy evidence, or
    a scientific result.
13. A content-addressed lifecycle-to-atom alignment contract with independent
    Python and TypeScript validation.  It rederives the exact 15/59/27/9
    lifecycle cardinalities, binds the exact canonical schema bytes, and keeps
    all lifecycle rows non-authoritative.  It exposes 46 direct but unbound
    projections, four assignment slots that must map to one assignment atom and
    four distinct forks, four arm-transition rows that are derived multi-atom
    projections, and four probe-response seals requiring a semantic adapter to
    probe trajectories, plus one delayed audit-release row for which schema v1
    has no canonical kind.  It also enumerates ten support kinds absent from
    lifecycle rows and classifies the current block seal as insufficient for
    production closure.  This closes a category-error risk, not the actual
    atom/content/provider evidence seam.
14. A distinct DNRD-5 v2 successor schema with 44 kinds, exactly one
    schema-relative owner per kind, and test-pinned canonical schema content of
    31,298 bytes with SHA-256
    `a921264c5d1b5d9186d291e6a17ddc0282ce4eaa8832b1a599b7237c23d4b357`.
    It adds the owned delayed `audit_release` and a distinct block/policy-bound
    audit-release capability kind, directly scopes revision/rollback decisions
    to block/assignment/fork, separates those precommit decisions from
    postcommit revision/rollback receipts, represents main-effect and
    evidence-seal consumption separately, and fixes schema-level receipt/restore
    cardinalities.  An atomic-batch instrument validates
    same-command typed/provenance dependencies, external pre-state/read-set
    closure, cycles, deterministic topological order, and exact dependency-edge
    hashes while retaining the unchanged generic evolution kernel.  A
    record-bound verifier recomputes actual canonical command/state/journal
    records and envelope bytes for one ADMIT or RESTORE main effect.  It and the
    separate four-effect protocol checker now share one postcommit receipt
    identity formula; the latter remains caller-declared consistency only.
    None of these instruments verifies a raw receipt-seal record, full
    journal-chain custody, a durable replay registry, complete block/arm
    semantics, Permit, occurrence, learning, or efficacy.

The focused Python and TypeScript checks pass.  Those checks establish that
the declared contracts reject their tested mutations.  They are not efficacy
observations and do not authorize a source freeze.

## Remaining source-freeze blockers

The following must exist and undergo another independent adversarial review
before Source A can be frozen:

1. The successor identity, owned `audit_release`, distinct precommit decisions
   and postcommit receipt kinds, schema-level manifest/seal references,
   same-batch dependency chronology, and record-bound ADMIT/RESTORE main-effect
   validator now exist without changing the preserved v1 bytes.  The remaining
   transaction closure is a raw postcommit receipt-seal command/record verifier,
   receipt-payload-to-effect-record byte binding, durable evidence-consumption
   and effect-record replay registry, full predecessor-chain custody, exact
   block/arm semantic validation, and raw audit-release/manifest/block-seal
   validation.  That semantic layer must equate each receipt decision or audit
   release capability with its evidence-consumption purpose instead of relying
   on kind-correct but potentially different reference paths.  The manifest
   must close actual lifecycle, call, provider,
   Permit, content, source, and build bytes rather than relying on its current
   schema-reference cardinalities.  The exact 59-row lifecycle adapter must
   bind three revision receipts and the restore transaction plus fourth
   rollback receipt without inventing row owners.
2. One production-shaped evidence vector and independently implemented judge
   must join task commitments, independent hidden/placebo entropy and custody,
   pre-outcome openings, actual evaluator records, all model-visible request
   bytes, provider calls, W0/forks, Permit, journal CAS, projections, and every
   lifecycle seal.  It must reconstruct the complete history `H` from actual
   allowed-input bytes, including public-task stratum categories, sealed
   trajectory, fixed instruction/RNG/runtime identities, and declared
   timing/capability projection, then independently verify the prespecified
   provenance, separation, and chronology evidence required for the declared
   conditional `theta`/placebo law.  A finite occurrence cannot empirically
   prove fairness or conditional independence.  The present validators remain
   separate slices.  The verifier closure must bind its source/tree, selected
   build output, semantic allowed-import graph, cross-language canonical corpus,
   and actual-byte evidence schema; the existing synthetic structural vectors
   do not meet that requirement.  The alignment audit is a mandatory input: all
   59 lifecycle rows must bind actual canonical atoms or declared derived slots
   without inventing row owners, and the judge must resolve the 4-to-1
   assignment mapping, arm-dependent transition sources, probe-trajectory
   adapter, ten support kinds, and underclosed block seal.
3. A production occurrence preflight must be the sole executor entrypoint and
   bind the frozen source/preregistration/runtime identities, 300-block
   universe, future-randomness receipt, custody commitments, nine-call plan,
   and provider evidence root before any model dispatch.  Source qualification
   must bind and independently recheck the source tree, semantic import/call
   graph, and selected build outputs rather than trusting the local textual
   allowlist alone.  The new schema-discriminated raw-submit guard does not by
   itself prevent altered repository source, a deep-module consumer outside the
   checked tree, a non-durable DNRD-shaped projection, or a test bootstrap from
   being mislabeled as a production occurrence.  The Python provider gateway
   must also require a preflight-issued single-use capability; its presently
   callable raw `execute` method is not yet the sole dispatcher.  The new pure
   structural scaffold is not this production preflight: its Q, Git/CI,
   Source-B, beacon, runtime, and no-prior-dispatch values are unopened caller
   descriptors, and it intentionally cannot make a Source-A qualification or
   chronology finding.
4. Policy, authorization, revocation, and evaluated time are content-addressed
   and internally closed, but no independently authenticated authority,
   revocation service, or trusted time receipt establishes their production
   currentness immediately before CAS.
5. Durable W0/fork identity, independent state recompilation, ACTIVE/SHAM
   admitted-shape matching, exact rollback, and behavior-projection
   non-traversability.
6. Production process/root isolation for the outcome, placebo, and probe
   custodians/evaluators plus
   denied network, undeclared file, session, prefix-cache, and cross-call paths.
7. Provider-side exactly-once/idempotency or an external dispatch witness,
   exact TLS/provider identity evidence, and explicit treatment of provider
   cache and ambiguous remote outcomes.  The gateway proves client-observed
   application bytes only, and separate roots remain outside its lock domain.
8. An independently implemented occurrence judge that verifies all integrity
   facts before handing the exact 300-block universe to the arithmetic module.
9. The model/provider reproducibility qualification.  Until the frozen
   block-level label-exchangeability and deterministic-potential-outcome
   assumption profile has its prespecified supporting evidence without a
   falsifying observation, the sign-test output must not be called finite-sample
   exact.  The occurrence
   judge must also verify that the selected beacon follows Source B, is bound to
   the frozen study, and independently rederives the prespecified uniform
   `S4` permutation and pairwise ACTIVE/control label-swap symmetry in every
   block.  One observed beacon cannot prove its declared uniformity or PRF law;
   that remains an explicit assumption.
10. The exactness-policy amendment resolves the R2 downgrade ambiguity in favor
   of an exact-test-required, no-fallback policy.  Source A needs prespecified
   finite evidence standards for the distinct assignment, deterministic
   potential-outcome, clone-exchangeability, consistency, no-interference, and
   evaluator assumptions.  Those checks may falsify or support the profile;
   they cannot prove unobserved provider or isolation behavior.  A missing or
   falsified exact-test profile produces the Source-A decision
   `SOURCE_A_REFUSED_EXACTNESS_UNQUALIFIED`.  The R2 normal lower bound remains a
   separate mandatory directional component, not a fallback, and needs its own
   block-cluster justification; otherwise the decision is
   `SOURCE_A_REFUSED_LCB_UNQUALIFIED`.  Any future standalone asymptotic route
   requires a separate reviewed revision with a block-cluster estimator,
   dependence and standard-error rules, all 300 valid complete blocks, no
   outcome- or discordance-based exclusion, and a scientific terminal distinct
   from every `ARITHMETIC_*` terminal.
   Before any disjoint reproducibility calls, a Q0 protocol/source/build/root
   commitment and Q-start marker must fix the corpus, replicates, comparator,
   order/randomness rule, budget, verifier, and failure handling.  Source A may
   bind the sealed Q closure afterward but may not retroactively authorize or
   tune Q from its outputs.
11. One-shot consumption is unique only within one recovered journal/root.
    Cloned roots or replayed stores can consume the same nonce, so production
    needs one globally selected occurrence root or an external uniqueness
    witness before the capability can be called globally one-shot.
12. The former unqualified legacy Python `sort_keys` plan-byte seam is narrowed
    by the reviewed `hswm-dnrd5-plan-json/v1` contract: exact printable-ASCII
    object keys, Unicode-scalar string values, safe integers, compact UTF-8,
    strict re-encoding, and explicit byte/depth/node limits are covered by a
    shared content-addressed KAT in two Python implementations and one
    TypeScript implementation.  Two complete plan known answers are rederived
    by the independent Python producer/consumer algorithms and by the
    independent TypeScript randomization rederiver and exact semantic validator;
    all three agree on both 300-block, 2,700-slot vectors and their raw-byte,
    blob-SHA, and root-plan-SHA values.  The remaining blocker is production
    binding: Source A must pin and independently recheck the selected source
    trees, TypeScript build output, semantic import graph, shared KAT, and
    actual-byte evidence schema.  Source A remains forbidden until that closure
    and the other blockers above close.

## Operational decision

No manual user hash echo is required for the remaining preparation.  No DNRD-5
source freeze, preregistration, future-randomness selection, semantic occurrence
marker, model call, efficacy analysis, content-addressed result receipt, or
`F1_R8_RESULTS_LOG.md` entry is warranted at this stage.  Work proceeds from
the checked successor schema, batch chronology, and main-effect record verifier
to raw receipt-seal and terminal block-record validation plus the exact
lifecycle adapter, then to production-shaped actual-byte closure, the
independent custody/occurrence judge, and the sole production preflight.  Even
a successful Source-A instrument audit may emit
only `SOURCE_A_INSTRUMENT_QUALIFIED_FUTURE_OCCURRENCE_EVIDENCE_REQUIRED`, not an
exactness, custody, or efficacy terminal.  The next decision point is another
source-freeze audit, not an execution attempt.  The conditional
byte-distribution statement above is algebra under a declared latent law, not
proof of a production placebo distribution.
