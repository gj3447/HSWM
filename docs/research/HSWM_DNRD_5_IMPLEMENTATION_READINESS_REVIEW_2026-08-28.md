# HSWM-DNRD-5 implementation-readiness review

- Date: 2026-08-28
- Review scope: post-R2 task, evaluator, randomization, lifecycle, provider,
  schema, and local durable-Permit candidate slices
- Decision: `NOT_READY_FOR_SOURCE_FREEZE / NOT_READY_FOR_PREREGISTRATION / NO_MODEL_CALLS`
- Scientific status: `DESIGN-INSTRUMENT PROGRESS / UNMEASURED / NO EFFECT RESULT`
- Governing design:
  [`HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md`](HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md)

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
   connection; the vector is contract evidence, not an occurrence.
7. A DNRD-5 canonical-atom V2 schema with 37 schema-approved kinds, exactly one
   responsibility owner per kind, typed references, exact four arms,
   actual-principal inequality, strict provenance, and a dedicated persistent
   `capability_consumption` atom.
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
   stale/altered-input integration tests pass.  This is not yet a mandatory
   runtime dispatcher, crash-fault proof, global capability ledger, or trusted
   external authority/time service.
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

The focused Python and TypeScript checks pass.  Those checks establish that
the declared contracts reject their tested mutations.  They are not efficacy
observations and do not authorize a source freeze.

## Remaining source-freeze blockers

The following must exist and undergo another independent adversarial review
before Source A can be frozen:

1. One production-shaped evidence vector and independently implemented judge
   must join task commitments, independent hidden/placebo entropy and custody,
   pre-outcome openings, actual evaluator records, all model-visible request
   bytes, provider calls, W0/forks, Permit, journal CAS, projections, and every
   lifecycle seal.  It must reconstruct the complete history `H` from actual
   allowed-input bytes, including public-task stratum categories, sealed
   trajectory, fixed instruction/RNG/runtime identities, and declared
   timing/capability projection, then independently establish the conditional
   `theta`/placebo source law.  The present validators remain separate slices.
2. The DNRD-5 durable submitter must become the mandatory dispatcher for every
   DNRD-5 state-changing command.  The public generic durable `submit` path can
   still be configured against the schema and bypass the dedicated Permit and
   consumption checks.  The one-shot atom is unique only within one recovered
   journal/root; cloned roots or replayed stores can consume the same nonce.
3. Policy, authorization, revocation, and evaluated time are content-addressed
   and internally closed, but no independently authenticated authority,
   revocation service, or trusted time receipt establishes their production
   currentness immediately before CAS.
4. Durable W0/fork identity, independent state recompilation, ACTIVE/SHAM
   admitted-shape matching, exact rollback, and behavior-projection
   non-traversability.
5. Production process/root isolation for the outcome, placebo, and probe
   custodians/evaluators plus
   denied network, undeclared file, session, prefix-cache, and cross-call paths.
6. Provider-side exactly-once/idempotency or an external dispatch witness,
   exact TLS/provider identity evidence, and explicit treatment of provider
   cache and ambiguous remote outcomes.  The gateway proves client-observed
   application bytes only, and separate roots remain outside its lock domain.
7. An independently implemented occurrence judge that verifies all integrity
   facts before handing the exact 300-block universe to the arithmetic module.
8. The model/provider reproducibility qualification.  Until block-level label
   exchangeability and deterministic potential outcomes are demonstrated, the
   sign-test output must not be called finite-sample exact.

## Operational decision

No manual user hash echo is required for the remaining preparation.  No DNRD-5
source freeze, preregistration, future-randomness selection, semantic occurrence
marker, model call, efficacy analysis, content-addressed result receipt, or
`F1_R8_RESULTS_LOG.md` entry is warranted at this stage.  Work proceeds to the
mandatory DNRD-5 dispatcher and production-shaped end-to-end custody/occurrence
judge; the next decision point is another source-freeze audit, not an execution
attempt.  The conditional byte-distribution statement above is algebra under a
declared latent law, not proof of a production placebo distribution.
