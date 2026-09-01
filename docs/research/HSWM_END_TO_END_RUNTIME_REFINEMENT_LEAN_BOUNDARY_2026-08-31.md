# HSWM end-to-end runtime refinement Lean boundary

> **Status:** `SECONDARY_AI_FORMAL_CONDITIONAL_REFINEMENT / LIVE_LOCAL_LEAN_ADMISSION_GATE / CHECKED_IN_TYPESCRIPT_NOT_UNIVERSALLY_REFINED / EMPIRICAL_EVIDENCE_ABSENT / SCIENTIFIC_UNJUDGED`
>
> **Target authority:**
> [`HSWM Constitution`](../canon/HSWM_CONSTITUTION_2026-08-20.md)
> and the target-preserving
> [`adaptive research strategy`](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)
>
> **Formal artifact:**
> [`HSWMEndToEndRuntimeRefinement.lean`](../../formal/HSWMEndToEndRuntimeRefinement.lean)
> and the concrete field-checker boundary
> [`HSWMCanonicalPermitEnvelope.lean`](../../formal/HSWMCanonicalPermitEnvelope.lean)
> and the derived structural certificate projection
> [`HSWMExecutionCertificateWire.lean`](../../formal/HSWMExecutionCertificateWire.lean),
> followed by the typed four-arm occurrence bridge
> [`HSWMCausalEfficacyBridge.lean`](../../formal/HSWMCausalEfficacyBridge.lean)
>
> **Predecessor boundaries:**
> [`atomic admission`](HSWM_ATOMIC_PERMIT_INVARIANT_ADMISSION_LEAN_2026-08-31.md),
> [`efficacy non-entailment`](HSWM_ATOMIC_ADMISSION_EFFICACY_NON_ENTAILMENT_2026-08-31.md),
> and the
> [`TypeScript refinement obstruction`](HSWM_TYPESCRIPT_LEAN_REFINEMENT_OBSTRUCTION_2026-08-31.md)

## 1. Canonical role

HSWM remains one token-native LLM-function macro-neural process. Runtime state,
Permit, invariant certificate, sealed trajectory, outcome observation, causal
judgment, admitted revision and changed next behavior are typed moments and
atoms in the same evolving schema-relative hypergraph. They are not separate
authority, learning or cognition subsystems.

The target loop is stronger than a successful state write:

```text
concrete pre-state and trusted head
  -> actually issued and authenticated current Permit
  -> one exact invariant-valid atomic revision
  -> externally true outcome and independently identified causal credit
  -> changed runtime LLM behavior on a sealed evaluation
```

No record name, status literal, digest or role inequality can supply the whole
loop by itself.

## 2. Target, present evidence and conceptual delta

The target is a real TypeScript/Effect execution that simulates the Lean
`AtomicLearnAdmission` relation and whose exact admitted revision improves an
LLM's behavior under a declared measurement contract. The present conceptual
delta is a narrower live local gate: real Permit/state/recovery preflight is
followed by an exact canonical request to an executable Lean admission kernel;
only its accepted successor response permits protected local publication. This
is a proved refinement of the bounded local Permit-commit model at the Lean
kernel/wire boundary, not a universal TypeScript/Effect refinement of
`AtomicLearnAdmission`.

The checked-in runtime still publishes fail-closed obstruction profiles, generic
read-only local eligibility and one separately bounded DNRD-5 local two-CAS
history whose success terminal explicitly denies provider occurrence, learning
and efficacy. The conditional theorem shape that a future full execution must
inhabit remains:

```text
accepted concrete execution certificate
  + exact runtime-state abstraction before and after
  + exact Permit issue occurrence in the certificate trace
  + signature-verifier soundness and authorized active key evidence
  + exactly one recovered successful canonical commit occurrence
  + externally true observation witness
  + operational independence and causal-support witness
  + sealed probe receipt matching independently evidenced before/after invocation semantics
  + strict score gain under one frozen score function
  -> Lean atomic admission
     and authenticated Permit
     and exact outcome/credit binding
     and bounded runtime LLM behavior improvement
```

The fixed `H/W/A/F/Pi` decomposition is not used. The bridge maps one
schema-relative transition, its responsibility owners and its typed evidence.

## 3. Concrete certificate and state refinement

`RuntimeExecutionTrace` contains one execution identity, a stable pre-execution
intent digest, a post-execution certificate digest, Permit-issue occurrences
and recovered successful-commit occurrences. The split prevents a digest
cycle: a Permit may sign the intent digest while the later certificate may
contain that Permit signature.
`ClaimedConcreteExecutionEvidence` requires:

- canonical certificate bytes and recovered post-state checks to have been
  accepted;
- one issue occurrence that exactly matches the Permit's authorizer, digest,
  head, target, revisions, authorization reference and scope;
- uniqueness of that exact Permit issue within the supplied trace;
- a successful-commit list containing exactly one occurrence, bound to the
  exact `AdmissionCommitWitness` and recovered successor head; and
- strict issue-before-commit-before-recovery indices within that bounded trace
  projection.

`ClaimedRuntimeAdmissionCertificate` additionally provides an abstraction
function from concrete runtime snapshots to Lean `CanonicalState`, exact
pre/post mappings, a supplied concrete-step semantics and every dependent
`AtomicAdmissionConditions` witness. Lean then proves the following conditional
projection:

```math
\mathrm{ClaimedRuntimeAdmissionCertificate}
\Longrightarrow
\mathrm{ConditionalRuntimeStepRefinesAtomicAdmission}
\Longrightarrow
\mathrm{AtomicLearnAdmission}.
```

It also proves that every successful commit named by the claimed certificate
is the one exact occurrence. This is certificate-level uniqueness. It is not a
proof of Node, SQLite, POSIX, hardware, crash, Byzantine or distributed
linearizability semantics. The certificate structure already carries the
atomic-admission conditions and an opaque concrete-step occurrence. Therefore
this theorem checks composition of supplied witnesses; it does not prove the
future checker sound, define TypeScript small-step semantics or establish that
the certificate corresponds to the real execution. Those are separate proof
obligations.

The certificate-digest binding is an explicit supplied semantics predicate.
This module does not implement canonical byte decoding, prove hash injectivity
or collision resistance, or prove that the execution identity is authentic.

## 4. Permit issue and authentication

The formal boundary distinguishes four layers:

| Layer | Formal object | Meaning |
| --- | --- | --- |
| issue occurrence | `PermitIssueOccurrence` | an exact Permit issue is present in the accepted execution trace |
| verifier result | `SignatureVerifier` | a supplied key/domain-separated-message/signature tuple returned `true` |
| verifier soundness | `SignatureVerifierSound` | verifier acceptance implies the declared signature meaning |
| key policy | `KeyAuthorization`, `KeyActiveAt` | that key is authorized for the authorizer and active at the issue point |

The abstract domain-separated signing message binds contract version, execution
identity, pre-execution intent digest, key-policy version, revocation epoch, Permit
digest, head, target, revisions, authorization, scope and issue index.
`soundVerifierAndKeyPolicyYieldPermitAuthentication` proves
`AuthenticatedPermitAt` only
when all four layers hold and the underlying atomic admission proves that the
Permit decision is both allowed and active. The verifier-soundness premise is
visible. Lean does not assume a cryptographic algorithm correct, identify a
human from a public key, establish key custody, query revocation or produce
trusted time.

The separately checked-in
[`canonical Permit authentication envelope`](HSWM_CANONICAL_PERMIT_AUTHENTICATION_ENVELOPE_2026-08-31.md)
now adds concrete TypeScript canonical bytes, an injected detached signer,
Ed25519 verification, trust-snapshot/key/time checks and exact binding checks.
Its separate Lean field-binding abstraction proves that fields accepted by the
modeled checker cannot float to another supplied execution, head, proposal,
invariant or nonce context. It is not a theorem that the TypeScript checker
refines Lean. The runtime result is only caller-trust/time-relative signature
verification, not an authoritative or atomic Permit occurrence.

## 5. Outcome truth and independent causal credit

`ExternalOutcomeSemanticWitness` binds one exact judgment already present in the
outcome package. It separately carries:

- instrument acceptance for world evidence, a preregistered criterion and a
  causal design;
- a semantic witness that the observation is externally true;
- operational-independence witnesses separating observation evaluator and
  causal adjudicator from actor, proposer and one another; and
- a semantic witness that the exact judgment causally supports the exact
  proposal.

Lean proves that this judgment is the same judgment consumed by the atomic
admission; two different `some judgment` values cannot satisfy the same package
binding. It then derives `IndependentCausalCredit` for that exact pair.

Truth and causality remain premises discharged by external evidence and a
declared identification model. This is intentional. The earlier countermodel
already proves that `.supports`, a digest and symbolic principal separation do
not entail external truth, real independence or causal support.

## 6. Revision-bound LLM behavior improvement

`BehaviorEvaluationReceipt` binds before/after model-configuration digests,
sealed suite digest, response-trace digests, exact predecessor and successor
state digests, evaluator, suite size and aggregate natural-number scores.
`RuntimeBehaviorMeasurementWitness` requires that:

- the suite was sealed before evaluation;
- the suite is nonempty and its digest and cardinality match;
- before/after model configuration is held fixed;
- both full response traces match their declared digests;
- both state digests match the concrete runtime snapshots through the same
  abstraction used by refinement;
- aggregate scores equal the frozen score function over the full declared
  runtime LLM response trace; and
- the aggregate after score is strictly larger than the aggregate before
  score.

Lean proves bounded aggregate strict improvement and then proves that at least
one probe in the suite has a different modeled runtime response. This
conclusion is deliberately narrow: it is one sealed suite under one supplied
behavior and score semantics. It is not proof that those abstractions equal a
real provider, universal improvement, future-distribution generalization,
consciousness, autonomous self-improvement or HSWM-wide efficacy.

The suite, model-configuration and response digest functions are also supplied
semantics. Their equalities are not a proof of canonical byte encoding,
injective hashing, collision resistance or real provider execution.

The final theorem `conditionalEvidenceBundleYieldsBoundedClaim` composes this
measurement with the exact claimed revision, authenticated Permit and exact
outcome/causal judgment. It also requires a separate
`RevisionBehaviorAttribution` witness; aggregate gain alone is not renamed as
causality. Thus the bounded claim cannot float free of the runtime pre/post
states or be attached to another proposal. The attribution predicate remains
an external identification premise, not something Lean derives from the score
increase.

The subsequent
[`causal-efficacy occurrence bridge`](HSWM_CAUSAL_EFFICACY_OCCURRENCE_LEAN_BRIDGE_2026-09-01.md)
replaces a free-standing one-suite attribution interface with a typed DNRD-5
occurrence. It binds three accepted execution-certificate-backed admissions,
the exact active successor and W0 control snapshots, typed proposal/probe
calls, sealed four-arm rows and row-derived exact-sign decisions. Outcome
truth, independent credit, real feedback inputs, state mediation, isolation,
actual rollback, LCB computation and causal identification remain separate
premises; no real occurrence is inferred from the new structure.

## 7. Machine-checked obstruction for the current TypeScript path

The declared end-to-end audit profile records one present fact: the runtime
publishes a fail-closed obstruction. Every positive evidence dimension remains
false:

| Obligation | Checked-in status |
| --- | --- |
| concrete runtime-state abstraction to Lean pre/post state | absent |
| canonical Permit issue occurrence | absent |
| authentication mechanism and fixed signed test vector | present, bounded |
| actual Permit issue under authoritative trust/key/time evidence | absent |
| syntactically cycle-free execution-certificate contract and Lean structural projection | present, decoded-field abstraction only |
| TypeScript/raw-byte execution-certificate checker refinement | absent |
| a protected local commit following an exact wire decision from the configured CLI, with the checked-in Lean executable exercised by integration tests | present, bounded local gate only; executable identity unpinned |
| one full canonical certificate-connected commit occurrence for this same transition | absent |
| externally true outcome evidence | absent |
| independently identified causal credit | absent |
| revision-bound LLM behavior improvement evidence | absent |
| typed 300-block four-arm occurrence contract and exact row-to-sign-gate derivation | present, conditional schema only; no inhabited real occurrence |

Lean proves:

```math
\neg\mathrm{ReadyForEndToEndRuntimeRefinement}
  (\mathrm{checkedInTypeScriptEndToEndProfile}).
```

This profile definition is a manual formal projection of the audited exact
source statuses. It is not extracted TypeScript semantics and does not prove
that Lean parsed or executed the source. The existing TypeScript obstruction
modules and exact-byte tests independently pin their own negative literals.

It also constructs an all-true metadata profile and pairs it with an explicitly
denied Permit for which atomic admission is impossible. Therefore even every
Boolean readiness flag being `true` does not entail a runtime transition or a
Lean proof object. The positive bridge requires dependent evidence, not a
promoted status record.

## 8. Why the requested unconditional proof cannot yet exist

Lean can verify a model, a checker and consequences of supplied evidence. It
cannot create historical execution, cryptographic custody, world truth,
evaluator independence, causal identification or LLM responses that did not
occur. In this checkout there is additionally no universal TypeScript-to-Lean
state simulation, no full certificate-to-commit connection and no actual
provider/evaluation path coupled to canonical revision. The local issuer and
gated commit path remain caller-relative and bounded, rather than a canonical
authority. Claiming an unconditional theorem now would
contradict both the implementation's exact status literals and the existing
non-entailment countermodels.

The positive theorem is deliberately assumption-carrying:

- the claimed certificate already contains the Lean atomic-admission
  conditions and an occurrence under a supplied runtime-step predicate;
- verifier soundness and key authorization/activity are explicit premises;
- the outcome witness already contains external truth, operational
  independence and causal-support propositions;
- the behavior witness already contains exact suite-score correspondences; and
- revision-to-behavior attribution is a separate supplied proposition.

Lean proves that these witnesses are mutually and exactly composed. It does not
manufacture or independently validate their real-world premises.

The current proved result is therefore two-sided:

1. the positive end-to-end implication is formally closed for any future exact
   evidence bundle that satisfies every premise; and
2. the present TypeScript/Effect path is not shown to instantiate that
   implication: it has a live bounded local admission gate, but lacks the
   full-state/source-level bridge and the remaining evidence obligations.

## 9. Required implementation and evidence sequence

The next valid route remains proof-first but must eventually cross into real
execution:

1. connect the frozen execution-intent/certificate wire contract to the live
   Lean-gated local commit path, then prove that its concrete checker refines
   the checked-in Lean structural model;
2. extend the implemented canonical Permit envelope and caller-configured
   Lean CLI into a separately scoped, pinned issuer/executor boundary with
   authoritative workload identity, trusted time,
   key rotation/revocation evidence and an independently replayed raw-byte
   verifier;
3. re-evaluate Permit and `Inv(S,c,S')` inside one genuinely atomic durable
   transaction, consume exact certificate identities and recover the exact
   successor before publishing success;
4. obtain independently operated world-outcome and causal-design evidence for
   the exact sealed trajectory and proposal;
5. run the real LLM before/after and controls under a frozen model, probe suite,
   score and stopping rule; and
6. feed the immutable execution/evidence bundle to the independent checker and
   instantiate the Lean theorem without changing any failure threshold.

Only steps 1 through 6 together can support a positive concrete refinement and
bounded behavioral-improvement claim. A scientific efficacy result would then
require its own preregistered result ceremony. This formal engineering phase
creates no research receipt and does not change the program's `UNJUDGED`
status.
